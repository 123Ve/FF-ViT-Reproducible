"""Run calibrated U3 and frozen U8 on identical complete held-out splits."""
import argparse
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import numpy as np
import torch
import u3_validation as u
from lut_accuracy import RealMoments, gelu_reference


def configure():
    os.environ["PYTHONDONTWRITEBYTECODE"]="1"
    torch.set_num_threads(4);torch.set_num_interop_threads(4)
    torch.manual_seed(0);np.random.seed(0)
    torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cudnn.allow_tf32=False
    torch.use_deterministic_algorithms(True)


def evaluate(artifact,ds,device,batch_size,path,limit=None):
    count=len(ds) if limit is None else min(len(ds),limit)
    loader=torch.utils.data.DataLoader(torch.utils.data.Subset(ds,list(range(count))),batch_size=batch_size,
        num_workers=4,shuffle=False,pin_memory=device.type=="cuda")
    correct=total=0;began=time.monotonic()
    with path.open("w",newline="") as stream,torch.inference_mode():
        writer=csv.writer(stream);writer.writerow(["index","path","label","prediction","correct"])
        for images,labels in loader:
            logits,_=u.exact.forward(images.to(device),artifact)
            predicted=logits.argmax(-1).cpu()
            for y,yp in zip(labels.tolist(),predicted.tolist()):
                writer.writerow([total,ds.samples[total][0],y,yp,int(y==yp)])
                correct+=int(y==yp);total+=1
            if total%256 < batch_size or total==count:
                print(json.dumps(dict(event="accuracy_progress",file=str(path.name),completed=total,total=count,
                    correct=correct,top1=100*correct/total,elapsed_seconds=time.monotonic()-began)),flush=True)
    if total!=count:raise ValueError("incomplete evaluation")
    return dict(sample_count=total,correct=correct,top1_percent=100*correct/total,
        complete_split=limit is None,unique_indices=total,elapsed_seconds=time.monotonic()-began,
        predictions=str(path),predictions_sha256=u.digest(path),
        numeric_mode="full integer HLS ABI replay, frozen signed W8/19-bit Head; not FPGA")


def natural_audit(name,artifact,params,ds,record,out,device):
    audit_params=[]
    for p,r in zip(artifact["blocks"],params):
        audit_params.append(dict(softmax=p["softmax"],score_scale=r["score_scale"],
            gelu_scalars=p["gelu_lut"]["scalars"],gelu_table=p["gelu_lut"]["table"],
            gelu_input_scale=r["gelu_input_scale"],gelu_output_scale=r["gelu_output_scale"]))
    audit=u.UnitAudit(name,audit_params)
    ln_codes=[u.CodeMoments() for _ in range(24)]
    ln_real=[RealMoments() for _ in range(24)]
    rsqrt=[RealMoments() for _ in range(24)]
    mismatch=[0]*24;samples=[]
    with torch.inference_mode():
        for number,index in enumerate(record["natural_indices"]):
            image,label=ds[index];samples.append(record["natural_samples"][number])
            x=u.exact.patch_forward(image.unsqueeze(0).to(device),artifact["patch"])
            for b,p in enumerate(artifact["blocks"]):
                previous=x;x,t=u.exact.block_forward(x,p,trace=True)
                audit.softmax(b,t["scores"]);audit.gelu(b,t["m1_raw"].cpu())
                for j,(value,output) in enumerate(((previous,t["ln1"]),(t["attention_residual"],t["ln2"]))):
                    r=params[b]["ln"][j];a=value.cpu().numpy().reshape(-1,192)
                    actual=output.cpu().reshape(-1,192)
                    ref=u.ln_numeric.fp32_reference(a,gamma=r["gamma"],beta=r["beta"],
                        input_scale=r["input_scale"],output_scale=r["output_scale"],eps=r["eps"])
                    finite=u.ln_numeric.fixed_layernorm(a,p[f"ln{j+1}"],input_bits=r["input_bits"])
                    mismatch[b*2+j]+=int((actual.numpy()!=finite["codes"]).sum())
                    ln_codes[b*2+j].add(actual,torch.from_numpy(ref["codes"]))
                    ln_real[b*2+j].add(actual.double()*r["output_scale"],torch.from_numpy(ref["real"]))
                    scales=u.ln_numeric.compare_batch(a,p[f"ln{j+1}"],input_bits=r["input_bits"],
                        gamma=r["gamma"],beta=r["beta"],input_scale=r["input_scale"],output_scale=r["output_scale"],eps=r["eps"])
                    # Attribution's LUT rsqrt scaling is exactly the previous audit definition.
                    attr=scales["attribution"]
                    rsqrt[b*2+j].add(torch.from_numpy(attr["lut_rsqrt"]),torch.from_numpy(attr["exact_mean_rsqrt"]))
            if (number+1)%16==0:print(json.dumps(dict(event="local_accuracy_progress",variant=out.name,images=number+1)),flush=True)
    if sum(mismatch):raise ValueError("native LN vs independent finite-width LN mismatch")
    image_count=len(samples)
    rows=audit.rows(image_count)
    for i,(code,real) in enumerate(zip(ln_codes,ln_real)):
        r=params[i//2]["ln"][i%2]
        rows.append(dict(dataset=name,instance=f"block{i//2:02d}.ln{i%2+1}",operator="LayerNorm",input_images=image_count,
            input_scale=r["input_scale"],output_scale=r["output_scale"],**code.result(),**real.result(),
            independent_integer_mismatches=mismatch[i]))
    u.write_csv(out / "unit_accuracy.csv",rows)
    u.write_csv(out / "rsqrt_accuracy.csv",[dict(dataset=name,instance=f"block{i//2:02d}.ln{i%2+1}",
        operator="LayerNorm_Rsqrt",input_images=image_count,unit="inverse_input_integer_code",**metric.result())
        for i,metric in enumerate(rsqrt)])
    np.savez_compressed(out / "gelu_input_histograms.npz",**{f"block{b:02d}":h.numpy() for b,h in enumerate(audit.gelu_hist)})
    u.save_json(out / "samples.json",samples)
    u.save_json(out / "unit_accuracy.json",dict(rows=rows,software_LN_independent_mismatches=sum(mismatch),
        reference="quantized float reference on same local integer input; real error also against continuous unclipped float",
        execution=dict(software="MEASURED",hls_csim="NOT_MEASURED",rtl_cosim="NOT_MEASURED",fpga="NOT_MEASURED")))
    exhaustive=[]
    for b,p in enumerate(audit_params):
        q=torch.arange(-1024,1024,dtype=torch.int64);sc=p["gelu_scalars"]
        prediction=u.exact.address_lut(q,sc,p["gelu_table"],32)
        ref,_=gelu_reference(q,p["gelu_input_scale"],p["gelu_output_scale"],name)
        metric=u.CodeMoments();metric.add(prediction,ref)
        exhaustive.append(dict(dataset=name,instance=f"block{b:02d}",operator="GELU",scope="EXHAUSTIVE_S11_2048",**metric.result()))
    u.write_csv(out / "gelu_exhaustive.csv",exhaustive)
    return rows


def run(name,out,args):
    out.mkdir(parents=True,exist_ok=False)
    spec=u.dataset_spec(name);device=torch.device(args.device)
    artifact=u.load_native_artifact(spec);params=u.reference_parameters(spec)
    files=[spec["weights"],spec["rom"],spec["checkpoint"],spec["calibration"],
        u.ROOT / "image1k_hls_s3_original/src/exact.py",Path(u.__file__),Path(__file__),
        u.ROOT / "validation/lut_float_accuracy_20261010/lut_accuracy.py",
        u.ROOT / "validation/ln_iotj_20261008/ln_numeric.py"]
    files += [spec["source"] / n for n in ("block0.cpp","fused_flash_attn.h","layernorm.h","quant.h","attn.h","mlp.h","matmul.h")]
    # Source templates for historical fixtures are also hashed; arithmetic replays
    # are established by matching saved dumps, not by assuming current src dates.
    for stage in ("stage4l_exact_softmax_aq","stage4f_exact_gelu","stage4m_exact_encoder"):
        files.append(spec["reports"] / stage / "report.json")
    sources={str(p):u.digest(p) for p in files}
    fixture=u.verify_historical_fixture(spec,artifact,torch.device("cpu"))
    fixture_gpu=u.verify_historical_fixture(spec,artifact,device)
    u.save_json(out / "historical_fixture_check.json",dict(cpu=fixture,execution_device=fixture_gpu))
    datasets,record=u.prepare_datasets(spec);u.save_json(out / "dataset_identity.json",record)
    print(json.dumps(dict(event="prepared",dataset=name,test_count=len(datasets["test"]),val_count=len(datasets["val"]),device=str(device))),flush=True)
    if args.calibrated:
        candidate,meta=u.exact.load_artifact(args.calibrated)
        for p in candidate["blocks"]:
            p["_internal_padding"]=p["_internal_padding"].tobytes();p["_tail_padding"]=p["_tail_padding"].tobytes()
        u.authorized_changes(u.encode_blocks(artifact["blocks"]),u.encode_blocks(candidate["blocks"]))
    else:candidate=u.calibrate_u3(artifact,datasets,params,out,device,args.batch_size)
    results=[]
    for variant,model in (("U8",artifact),("U3",candidate)):
        dest=out / variant;dest.mkdir()
        metrics={}
        for split in ("val","test"):
            metrics[split]=evaluate(model,datasets[split],device,args.batch_size,dest / (split+"_predictions.csv"),args.limit)
            results.append(dict(dataset=name,variant=variant,split=split,**metrics[split]))
            u.save_json(dest / "accuracy.json",metrics)
        natural_audit(name,model,params,datasets["test"],record,dest,device)
    u.write_csv(out / "accuracy_comparison.csv",results)
    if any(u.digest(Path(p))!=h for p,h in sources.items()):raise ValueError("original/source file changed during run")
    u.save_json(out / "manifest.json",dict(dataset=name,sources=sources,command=sys.argv,
        gpu=torch.cuda.get_device_name(device) if device.type=="cuda" else None,torch_version=torch.__version__,
        preserved_sources=True,training=False,scope="same weights/ROM, calibrated Softmax U3+AQ ONLY; not frozen E07 board parameter identity",
        accuracy=results,states=dict(software="MEASURED",new_hls_csim="NOT_MEASURED",rtl_cosim="NOT_MEASURED",fpga="NOT_MEASURED")))
    print(json.dumps(dict(event="complete",dataset=name,accuracy=results)),flush=True)


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument("--dataset",choices=["plantvillage","nwpu"],required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--device",default="cuda")
    parser.add_argument("--batch-size",type=int,default=16)
    parser.add_argument("--limit",type=int)
    parser.add_argument("--calibrated",type=Path)
    args=parser.parse_args();configure()
    out=args.output.resolve()
    if not out.is_relative_to(u.HERE) or out==u.HERE:raise ValueError("outputs must remain in independent validation directory")
    run(args.dataset,out,args)


if __name__=="__main__":main()
