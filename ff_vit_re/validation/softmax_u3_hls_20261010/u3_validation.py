"""Independent U3 probability experiment; frozen weights/ROM are read only.

Replay the actual fused FlashAttention HLS ABI, not a floating/fake-quant
network. Native int overflow follows two's-complement (-fwrapv) semantics.
GPU GEMM is allowed only under the exact integer mantissa bounds of exact.py.
"""
from __future__ import annotations
import argparse
import copy
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import numpy as np
import torch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "quantization_final/scripts"),
                str(ROOT / "validation/lut_float_accuracy_20261010"),
                str(ROOT / "validation/ln_iotj_20261008")]
from image1k_hls_s3_original.src import exact
from lib import hls_abi
from verify_patch_bitexact import parse_c_array
from lut_accuracy import UnitAudit, write_csv, CodeMoments
import ln_numeric


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for data in iter(lambda: f.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def dataset_spec(name):
    if name == "plantvillage":
        base = ROOT / "quantization_final"
        run = base / "artifacts"
        deploy = base / "deployment"
        return dict(name=name, base=base, run=run, deploy=deploy,
            weights=deploy / "weights.bin", rom=deploy / "fixed_patch_head_rom.h",
            checkpoint=base / "checkpoints/stage4j_attention_qat/best_attention_qat.pth",
            reports=base / "reports", calibration=base / "calibration/calib_manifest.json",
            csim=Path("/home/user/Desktop/FF_Vit/flash_vit_2/flash_vit/vit_plantvillage_bitaccurate/hls/csim/build"),
            classes=38, source=Path("/home/user/Desktop/FF_Vit/flash_vit_2/src"))
    if name != "nwpu":
        raise ValueError("only PlantVillage and NWPU supported")
    base = ROOT / "archive/nwpu_resisc45_ffvit"
    run = base / "runs/nwpu_seed20260923"
    deploy = base / "deployment/nwpu_seed20260923"
    return dict(name=name, base=base, run=run, deploy=deploy,
        weights=deploy / "weights.bin", rom=deploy / "fixed_patch_head_rom.h",
        checkpoint=run / "stage4j_attention_qat/best_attention_qat.pth",
        reports=run, calibration=base / "metadata/calibration.json",
        csim=base / "validation/task7/canonical_dumps", classes=45,
        source=Path("/home/user/Desktop/FF_Vit/flash_vit_2/src_resisc45"))


def decode_blocks(raw):
    if len(raw) != hls_abi.WEIGHTS_BIN_BYTES:
        raise ValueError("native weights ABI size mismatch")
    blocks = []
    for b in range(12):
        offset = b * 231008
        def read(dtype, shape):
            nonlocal offset
            n = int(np.prod(shape)); dt = np.dtype(dtype)
            a = np.frombuffer(raw, dtype=dt, count=n, offset=offset).copy().reshape(shape)
            offset += dt.itemsize * n
            return a
        def matrix(shape):
            nonlocal offset
            n = int(np.prod(shape)) // 2
            a = exact.unpack3(raw[offset:offset+n], shape)
            offset += n
            return a
        p = {}
        for name in ("q", "k", "v"):
            p[name+"_w"] = matrix((192, 192))
        for name in ("q", "k", "v"):
            p[name+"_b"] = read("<i2", (192,))
        p["o_w"] = matrix((192, 192)); p["o_b"] = read("<i2", (192,))
        p["attn_residual"] = read("<i4", (3,))
        def norm():
            return dict(scalars=read("<i4", (7,)), lnw=read("<i4", (192,)),
                        lnb=read("<i8", (192,)), rsqrt_table=read("<i4", (128,)))
        p["ln1"] = norm()
        for name in ("q", "k", "v", "a"):
            p[name+"_lut"] = dict(scalars=read("<i4", (4,)), table=read("i1", (64,)))
        p["softmax"] = dict(scalars=read("<i4", (14,)), exp=read("<u2", (32,)),
                            recip1=read("u1", (64,)), recip2=read("i1", (64,)), output_scale=1/256)
        if offset != b*231008 + 78688:
            raise ValueError("Attention ABI offsets differ")
        p["m1_w"] = matrix((768, 192)); p["m1_b"] = read("<i2", (768,))
        p["m2_w"] = matrix((192, 768)); p["m2_b"] = read("<i2", (192,))
        p["mlp_residual"] = read("<i4", (2,))
        p["ln2"] = dict(scalars=read("<i4", (7,)), lnw=read("<i4", (192,)))
        p["_internal_padding"] = raw[offset:offset+4]; offset += 4
        p["ln2"].update(lnb=read("<i8", (192,)), rsqrt_table=read("<i4", (128,)))
        p["gelu_lut"] = dict(scalars=read("<i4", (4,)), table=read("u1", (64,)))
        p["_tail_padding"] = raw[offset:offset+8]; offset += 8
        if offset != (b+1)*231008:
            raise ValueError("MLP ABI offsets differ")
        blocks.append(p)
    return blocks


def encode_blocks(blocks):
    A = {}
    def field(name, values):
        A[name] = np.stack(values)
    for prefix, key in (("attn", "ln1"), ("mlp", "ln2")):
        for target, source in (("ln_scalars", "scalars"), ("lnw", "lnw"),
                               ("lnb", "lnb"), ("rsqrt", "rsqrt_table")):
            field(prefix+"_"+target, [p[key][source] for p in blocks])
    field("attn_scalars", [p["attn_residual"] for p in blocks])
    field("mlp_scalars", [p["mlp_residual"] for p in blocks])
    for name, prefix in (("q", "qq"), ("k", "kq"), ("v", "vq"), ("a", "aq"), ("gelu", "ge")):
        for key in ("scalars", "table"):
            field(prefix+"_"+key, [p[name+"_lut"][key] for p in blocks])
    for name in ("scalars", "exp", "recip1", "recip2"):
        field("softmax_"+name, [p["softmax"][name] for p in blocks])
    out = bytearray()
    for b, p in enumerate(blocks):
        a = hls_abi.build_attn_struct(p, A, b)
        m = bytearray(hls_abi.build_mlp_struct(p, A, b))
        m[150180:150184] = p["_internal_padding"]
        m[-8:] = p["_tail_padding"]
        out.extend(a); out.extend(m)
    return bytes(out)


def authorized_changes(old, new):
    if len(old) != 2772096 or len(new) != len(old):
        raise ValueError("ABI size mismatch")
    changed = np.frombuffer(old, np.uint8) != np.frombuffer(new, np.uint8)
    allowed = np.zeros(len(old), dtype=bool)
    for b in range(12):
        # AQ scalars+table and Softmax scalars+tables. No other parameters.
        allowed[b*231008+78360:b*231008+78688] = True
    bad = int(np.count_nonzero(changed & ~allowed))
    if bad:
        raise ValueError(f"unauthorized byte changes: {bad}")
    return dict(changed_bytes=int(changed.sum()), unauthorized_byte_changes=bad,
                permitted_block_byte_interval=[78360, 78688],
                preserved="all six W3 matrices/biases, LN1/LN2, GELU, both residuals, padding; Patch/Head ROM")


def load_native_artifact(spec):
    rom = spec["rom"]
    shape = {"PATCH_WEIGHT": (192,768), "PATCH_BIAS": (196,192), "PATCH_CLS": (192,),
             "PATCH_SCALARS": (4,), "HEAD_LN_SCALARS": (8,), "HEAD_LNW": (192,),
             "HEAD_LNB": (192,), "HEAD_RSQRT": (128,), "HEAD_WEIGHT": (1000,192), "HEAD_BIAS": (1000,)}
    a = {name: parse_c_array(rom, name, size) for name, size in shape.items()}
    artifact = dict(patch=dict(weight_code=a["PATCH_WEIGHT"], bias_raw=a["PATCH_BIAS"],
        cls_raw=a["PATCH_CLS"], shift=int(a["PATCH_SCALARS"][0])),
        head={name.lower():a[name] for name in shape if name.startswith("HEAD")},
        blocks=decode_blocks(spec["weights"].read_bytes()))
    if encode_blocks(artifact["blocks"]) != spec["weights"].read_bytes():
        raise ValueError("full native ABI roundtrip failed")
    return artifact


def verify_historical_fixture(spec, artifact, device):
    build = spec["csim"]
    input_path = spec["deploy"] / "input.bin"
    codes = np.fromfile(input_path, dtype="<i4").reshape(196,768)
    image = torch.nn.functional.fold(torch.from_numpy(codes.T.copy()).float().unsqueeze(0),
        (224,224), (16,16), stride=(16,16)).to(device)/64
    boundaries = {}
    def check(name, actual):
        path = build / ("hls_"+name+".bin")
        if name == "patch_out" and not path.exists():
            path = build / "hls_patch.bin"
        expected = np.fromfile(path, dtype="<i4").astype(np.int64)
        actual = actual.detach().cpu().numpy()
        if actual.ndim == 3:
            actual = actual.reshape(98,2,192).transpose(0,2,1)
        actual = actual.reshape(-1)
        if actual.size != expected.size:
            raise ValueError("historical boundary size mismatch")
        boundaries[name] = dict(values=int(actual.size), mismatches=int((actual != expected).sum()),
                                source=str(path), sha256=digest(path))
    with torch.inference_mode():
        x = exact.patch_forward(image, artifact["patch"]); check("patch_out", x)
        for b,p in enumerate(artifact["blocks"]):
            x,_ = exact.block_forward(x,p); check(f"block{b}_out", x)
        check("head_input", x[:,0])
        p = artifact["head"]
        normalized = exact.layernorm(x[:,0], dict(scalars=p["head_ln_scalars"][:7],
            lnw=p["head_lnw"],lnb=p["head_lnb"],rsqrt_table=p["head_rsqrt"]),input_bits=13,head=True)
        check("head_ln", normalized)
        logits = exact.wrap(exact.matmul(normalized,exact.integer(p["head_weight"],device).t())+
            exact.integer(p["head_bias"],device),19); check("logits",logits)
    result = dict(boundaries=boundaries, checked_integer_count=sum(r["values"] for r in boundaries.values()),
        mismatches=sum(r["mismatches"] for r in boundaries.values()),
        scope="fresh software replay vs saved historical U8 HLS C-sim dumps; NOT a new C-sim run",
        weights_sha256=digest(spec["weights"]), rom_sha256=digest(spec["rom"]))
    if result["mismatches"]:
        raise ValueError("HLS fixture mismatch: "+json.dumps(result))
    return result


def fit_u3_softmax(scores, old, *, score_scale):
    """Calibrate scale/reciprocal only, preserving the frozen EXP table/address."""
    x = exact.integer(scores).cpu().reshape(-1,scores.shape[-1])
    if len(x)>4096:
        x=x[torch.linspace(0,len(x)-1,4096).long()]
    probability = torch.softmax(x.double()*score_scale,-1)
    # Probability-distribution MSE only; no validation labels or test selection.
    hist = torch.histc(probability.float(),bins=8192,min=0,max=1).double()
    centers=(torch.arange(8192,dtype=torch.float64)+.5)/8192
    maxp=float(probability.max())
    candidates=np.geomspace(max(maxp/7/64,1e-5),max(maxp/7,1e-5),128)
    errors=[float(((torch.round(centers/float(s)).clamp(0,7)*float(s)-centers)**2*hist).sum()/hist.sum()) for s in candidates]
    scale=float(candidates[int(np.argmin(errors))])
    sc=old["scalars"].copy()
    exp = exact.address_lut(exact.wrap(x.max(-1,keepdim=True).values-x,11),sc[:3],old["exp"],8,False)
    acc=exact.wrap(exp.sum(-1),23,False)
    one=exact.wrap((acc+int(sc[3])) >> int(sc[4]),9,False)
    two=exact.wrap((acc+int(sc[8])) >> int(sc[9]),7)
    region=one>int(sc[5])
    target=torch.round(probability/scale).clamp(0,7).long()
    best=None
    for shift in range(8,25):
        # Reciprocal storage stays U8 even when probability output is U3.
        desired=torch.round((1 << shift)/(acc.clamp_min(1).double()*scale)).clamp(0,255)
        tables=[]
        for addr,mask,bound in ((one,~region,int(sc[5])),(two,region,int(sc[10]))):
            addr=addr.clamp(0,bound)
            counts=torch.bincount(addr[mask],minlength=64)
            sums=torch.bincount(addr[mask],weights=desired[mask],minlength=64)
            t=(sums/counts.clamp_min(1)).round().long(); used=torch.where(counts>0)[0]
            # Empty bank fallback is analytic at its original address midpoint.
            for i in torch.where(counts==0)[0]:
                if len(used): t[i]=t[used[torch.argmin(abs(used-i))]]
                else:
                    k=3 if len(tables)==0 else 8
                    den=max(1,((int(i)<<int(sc[k+1]))-int(sc[k])+(1 << int(sc[k+1]))//2))
                    t[i]=min(255,round((1 << shift)/(den*scale)))
            tables.append(t.numpy().astype(np.uint8))
        candidate=sc.copy(); candidate[6]=candidate[11]=1 << (shift-1)
        candidate[7]=candidate[12]=shift;candidate[13]=3
        pred=exact.fused_softmax(x,candidate,old["exp"],*tables)
        mse=float(((pred-target).double()**2).mean())
        if best is None or mse<best[0]:best=(mse,candidate,tables)
    mse,sc,tables=best
    return dict(scalars=sc,exp=old["exp"].copy(),recip1=tables[0],recip2=tables[1].view(np.int8),output_scale=scale),dict(
        fitted_rows=len(x),score_scale=score_scale,output_scale=scale,scale_candidates=128,
        float_grid_mse=min(errors),lut_code_mse=mse,final_shift=int(sc[7]),
        preserved="EXP and reciprocal address mappings",probability_bits=3,reciprocal_bits=8)


def fit_aq_pairs(counts):
    # Same majority-code objective/address search as the original Stage4L fitter,
    # vectorized aggregation. Input S11, cursor S10 BEFORE clamp, table S3.
    totals=counts.sum(1);xs=np.arange(-1024,1024,dtype=np.int64)[totals>0]
    pc=counts[totals>0];modal=pc.argmax(1)-4;moving=(modal>-4)&(modal<3)
    xlo=int(xs[moving].min() if moving.any() else xs.min());best=None
    for shift in range(11):
        step=1 << shift
        for offset in (0,1,2,4,8):
            for phase in range(step):
                bias=(1+offset)*step-xlo+phase; raw=(xs+bias)>>shift
                cursor=(raw+512)%1024-512; addr=cursor.clip(0,63)
                agg=np.zeros((64,8),np.int64);np.add.at(agg,addr,pc)
                used=np.flatnonzero(agg.sum(1)>0); table=agg.argmax(1)-4
                for i in np.flatnonzero(agg.sum(1)==0):table[i]=table[used[np.argmin(abs(used-i))]]
                correct=int(agg.max(1).sum()); wrap=int(totals[totals>0][(raw<-512)|(raw>511)].sum())
                key=(-correct,wrap,shift)
                if best is None or key<best[0]:best=(key,bias,shift,table)
    key,bias,shift,table=best
    return dict(scalars=np.array([bias,shift,63,0],np.int32),table=table.astype(np.int8)),dict(
        fitted_codes=int(counts.sum()),target="FP64 softmax(same integer QK score) times same V, quantized to frozen S3 A scale",
        mismatch_rate=1+key[0]/counts.sum(),cursor_wrap_rate=key[1]/counts.sum())


class PathDataset(torch.utils.data.Dataset):
    def __init__(self, samples, classes, transform):
        self.samples, self.classes, self.transform = samples, classes, transform
    def __len__(self):return len(self.samples)
    def __getitem__(self,i):
        from PIL import Image
        path,label=self.samples[i]
        with Image.open(path) as image:return self.transform(image.convert("RGB")),label


def prepare_datasets(spec):
    from torchvision.datasets import ImageFolder
    from torchvision import transforms
    transform=transforms.Compose([transforms.Resize(256),transforms.CenterCrop(224),
        transforms.ToTensor(),transforms.Normalize((.485,.456,.406),(.229,.224,.225))])
    record={}; datasets={}
    if spec["name"]=="plantvillage":
        for split in ("test","val"):
            datasets[split]=ImageFolder(spec["base"] / "datasets/PlantVillage/splits" / split,transform=transform)
        manifest=json.loads(spec["calibration"].read_text())
        calibration=PathDataset([(r["path"],r["class_index"]) for r in manifest["samples"]],manifest["classes"],transform)
        test_hashes={digest(p) for p,_ in datasets["test"].samples}
        val_hashes={digest(p) for p,_ in datasets["val"].samples}
        calibration_hashes=[digest(p) for p,_ in calibration.samples]
    else:
        from archive.nwpu_resisc45_ffvit.src.manifest_dataset import load_manifest_bundle,ManifestImageDataset
        bundle=load_manifest_bundle(spec["base"] / "metadata")
        source=ROOT / "archive/Dataset"
        for split in ("test","val"):
            ds=ManifestImageDataset(source,bundle.records_for(split),transform)
            ds.classes=list(bundle.classes);ds.samples=[(str(source / r.relative_path),r.label) for r in ds.records]
            datasets[split]=ds
        calibration=ManifestImageDataset(source,bundle.records_for("calibration"),transform)
        calibration.classes=list(bundle.classes);calibration.samples=[(str(source / r.relative_path),r.label) for r in calibration.records]
        test_hashes={r.sha256 for r in datasets["test"].records}
        val_hashes={r.sha256 for r in datasets["val"].records}
        calibration_hashes=[r.sha256 for r in calibration.records]
    if calibration.classes!=datasets["test"].classes or calibration.classes!=datasets["val"].classes:
        raise ValueError("calibration and evaluation class order differs")
    # No held-out-image content may participate in U3 fitting.
    eligible=[i for i,h in enumerate(calibration_hashes) if h not in test_hashes|val_hashes]
    chosen=np.linspace(0,len(eligible)-1,256,dtype=np.int64)
    indices=[eligible[int(i)] for i in chosen]
    datasets["calibration"]=torch.utils.data.Subset(calibration,indices)
    historical_path=ROOT / "validation/ln_iotj_20261008/outputs/final128" / spec["name"] / "samples.json"
    old=json.loads(historical_path.read_text())["samples"]
    if len(old)!=128:raise ValueError("historical sample list not 128")
    natural_indices=[r["index"] for r in old]
    for r,i in zip(old,natural_indices):
        image,label=datasets["test"][i]
        path,y=datasets["test"].samples[i]
        if label!=r["label"] or digest(path)!=r["source_image_sha256"] or hashlib.sha256(image.numpy().tobytes()).hexdigest()!=r["transformed_fp32_sha256"]:
            raise ValueError("128 natural-image identity changed")
    record.update(transform=repr(transform),classes=calibration.classes,
        test_count=len(datasets["test"]),val_count=len(datasets["val"]),
        natural_indices=natural_indices,natural_samples=old,
        calibration_manifest=str(spec["calibration"]),calibration_manifest_sha256=digest(spec["calibration"]),
        source_calibration_count=len(calibration),eligible_calibration_count=len(eligible),
        selected_calibration_count=len(indices),calibration_selection="256 uniform indices in original train calibration manifest, excluding test/val identical bytes",
        calibration_indices=indices,selected_calibration_test_sha256_overlap=len({calibration_hashes[i] for i in indices}&test_hashes),
        selected_calibration_val_sha256_overlap=len({calibration_hashes[i] for i in indices}&val_hashes),
        calibration_samples=[dict(index=i,path=calibration.samples[i][0],label=calibration.samples[i][1],sha256=calibration_hashes[i]) for i in indices])
    return datasets,record


def reference_parameters(spec):
    sm=json.loads((spec["reports"] / "stage4l_exact_softmax_aq/report.json").read_text())["blocks"]
    ge=json.loads((spec["reports"] / "stage4f_exact_gelu/report.json").read_text())["blocks"]
    ln=json.loads((ROOT / "validation/ln_iotj_20261008/outputs/final128" / spec["name"] / "summary.json").read_text())["instances"]
    saved=torch.load(spec["checkpoint"],map_location="cpu",weights_only=True)
    state=saved["student_state"]
    params=[]
    for b in range(12):
        norms=[]
        for j in range(2):
            row=ln[b*2+j]
            # State prefixes differ across saved wrappers; require a unique suffix.
            suffix=f"blocks.{b}.norm{j+1}.weight"
            key=[k for k in state if k.endswith(suffix)]
            if len(key)!=1:raise ValueError("nonunique LN checkpoint binding")
            norms.append(dict(gamma=state[key[0]].numpy(),beta=state[key[0].replace("weight","bias")].numpy(),
                input_scale=row["input_scale"],output_scale=row["output_scale"],eps=row["eps"],input_bits=row["input_bits"]))
        p=sm[str(b)];g=ge[str(b)]
        params.append(dict(score_scale=p["q_scale"]*p["k_scale"]*p["attn_scale"],
            v_scale=p["v_scale"],a_scale=p["a_scale"],ln=norms,
            gelu_input_scale=g["m1_int11_scale"],gelu_output_scale=g["gelu_uint3_scale"]))
    return params


def qkv_forward(x,p):
    ln=exact.layernorm(x,p["ln1"],input_bits=13)
    result=[]
    for name,bits in (("q",12),("k",11),("v",11)):
        raw=exact.wrap(exact.matmul(ln,exact.integer(p[name+"_w"],x.device).t())+exact.integer(p[name+"_b"],x.device),bits)
        lut=p[name+"_lut"]
        result.append(exact.address_lut(raw,lut["scalars"],lut["table"],9).reshape(-1,196,3,64).permute(0,2,1,3))
    return result


def calibration_event(report):
    return dict(event="calibrated_block", **report)


def calibrate_u3(artifact, datasets, params, out, device, batch_size):
    loader=torch.utils.data.DataLoader(datasets["calibration"],batch_size=batch_size,num_workers=4,shuffle=False)
    xs=[]
    with torch.inference_mode():
        for images,_ in loader:xs.append(exact.patch_forward(images.to(device),artifact["patch"]).cpu())
    x=torch.cat(xs);candidate=copy.deepcopy(artifact);reports=[]
    for b,p in enumerate(candidate["blocks"]):
        started=time.monotonic();scores_sample=[]
        # Propagated U3 earlier blocks, complete image contexts; uniform row sample.
        with torch.inference_mode():
            for batch in x.split(batch_size):
                q,k,v=qkv_forward(batch.to(device),p)
                s=exact.matmul(q,k.transpose(-1,-2)).reshape(-1,196)
                take=torch.linspace(0,len(s)-1,min(128,len(s)),device=device).long()
                scores_sample.append(s[take].cpu())
        sm,sm_report=fit_u3_softmax(torch.cat(scores_sample),p["softmax"],score_scale=params[b]["score_scale"])
        p["softmax"]=sm;pairs=np.zeros((2048,8),np.int64)
        with torch.inference_mode():
            for batch in x.split(batch_size):
                q,k,v=qkv_forward(batch.to(device),p);s=exact.matmul(q,k.transpose(-1,-2))
                rq=exact.fused_softmax(s,sm["scalars"],sm["exp"],sm["recip1"],sm["recip2"])
                raw=exact.wrap(exact.matmul(rq,v),11)
                # FP64 reference only trains the AQ table. It is NOT the execution path.
                target=torch.round(torch.matmul(torch.softmax(s.double()*params[b]["score_scale"],-1),v.double())*
                    params[b]["v_scale"]/params[b]["a_scale"]).clamp(-4,3).long()
                counts=torch.bincount(((raw+1024)*8+(target+4)).reshape(-1),minlength=16384)
                pairs+=counts.cpu().numpy().reshape(2048,8)
        aq,aq_report=fit_aq_pairs(pairs);p["a_lut"]=aq
        next_x=[]
        with torch.inference_mode():
            for batch in x.split(batch_size):next_x.append(exact.block_forward(batch.to(device),p)[0].cpu())
        x=torch.cat(next_x)
        reports.append(dict(block=b,softmax=sm_report,aq=aq_report,elapsed_seconds=time.monotonic()-started))
        print(json.dumps(calibration_event(reports[-1])),flush=True)
    payload=encode_blocks(candidate["blocks"])
    changes=authorized_changes(encode_blocks(artifact["blocks"]),payload)
    (out / "weights_u3.bin").write_bytes(payload)
    # Store portable parameter arrays, scalar scales and the frozen Patch/Head.
    portable=copy.deepcopy(candidate)
    for p in portable["blocks"]:
        p["_internal_padding"]=np.frombuffer(p["_internal_padding"],np.uint8).copy()
        p["_tail_padding"]=np.frombuffer(p["_tail_padding"],np.uint8).copy()
    exact.save_artifact(out / "u3_artifact",portable,dict(dataset=out.name,experiment="softmax_U3_only_with_AQ_refit",training=False,
        hls_csim="NOT_MEASURED",rtl_cosim="NOT_MEASURED",fpga="NOT_MEASURED"))
    save_json(out / "calibration_report.json",dict(blocks=reports,changes=changes,labels_used=False))
    return candidate


def main():
    raise SystemExit("Use run_experiment.py")


if __name__=="__main__":main()
