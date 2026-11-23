"""Software-only, same-input nonlinear accuracy audit for three FF-ViT models.

All outputs are written below this validation directory. Original models, LUTs,
HLS sources and prior evidence are read only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sys

import numpy as np
import torch


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "validation/ln_iotj_20261008"))
from image1k_hls_s3_original.src import exact


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class CodeMoments:
    def __init__(self) -> None:
        self.count = self.sum_abs = self.sum_sq = self.max_abs = 0
        self.exact_count = self.within_one_count = 0

    def add(self, observed: torch.Tensor, reference: torch.Tensor) -> None:
        if observed.shape != reference.shape:
            raise ValueError("observed/reference shapes differ")
        difference = (observed.to(torch.int64) - reference.to(torch.int64)).abs()
        self.count += difference.numel()
        self.sum_abs += int(difference.sum())
        self.sum_sq += int((difference * difference).sum())
        self.max_abs = max(self.max_abs, int(difference.max()))
        self.exact_count += int((difference == 0).sum())
        self.within_one_count += int((difference <= 1).sum())

    def add_histogram(self, observed: torch.Tensor, reference: torch.Tensor,
                      histogram: torch.Tensor) -> None:
        difference = (observed.to(torch.int64) - reference.to(torch.int64)).abs()
        histogram = histogram.to(torch.int64)
        if difference.shape != histogram.shape:
            raise ValueError("histogram and code-domain shapes differ")
        self.count += int(histogram.sum())
        self.sum_abs += int((histogram * difference).sum())
        self.sum_sq += int((histogram * difference * difference).sum())
        active = difference[histogram > 0]
        self.max_abs = max(self.max_abs, int(active.max()) if active.numel() else 0)
        self.exact_count += int(histogram[difference == 0].sum())
        self.within_one_count += int(histogram[difference <= 1].sum())

    def result(self) -> dict:
        if not self.count:
            raise ValueError("no observed codes")
        return dict(count=self.count, mae_lsb=self.sum_abs / self.count,
                    rmse_lsb=math.sqrt(self.sum_sq / self.count),
                    max_ae_lsb=self.max_abs, exact_rate=self.exact_count / self.count,
                    within_1_lsb_rate=self.within_one_count / self.count)


class RealMoments:
    def __init__(self) -> None:
        self.count = 0
        self.sum_abs = self.sum_sq = self.max_abs = 0.0

    def add(self, observed: torch.Tensor, reference: torch.Tensor) -> None:
        delta = (observed.to(torch.float64) - reference.to(torch.float64)).abs()
        self.count += delta.numel()
        self.sum_abs += float(delta.sum())
        self.sum_sq += float((delta * delta).sum())
        self.max_abs = max(self.max_abs, float(delta.max()))

    def add_histogram(self, observed: torch.Tensor, reference: torch.Tensor,
                      histogram: torch.Tensor) -> None:
        delta = (observed.to(torch.float64) - reference.to(torch.float64)).abs()
        weights = histogram.to(torch.float64)
        self.count += int(histogram.sum())
        self.sum_abs += float((weights * delta).sum())
        self.sum_sq += float((weights * delta * delta).sum())
        active = delta[histogram > 0]
        self.max_abs = max(self.max_abs, float(active.max()) if active.numel() else 0)

    def result(self) -> dict:
        if not self.count:
            raise ValueError("no observed values")
        return dict(real_mae=self.sum_abs / self.count,
                    real_rmse=math.sqrt(self.sum_sq / self.count),
                    real_max_ae=self.max_abs)


def evaluate_softmax(scores: torch.Tensor, scalars: np.ndarray,
                     exp_table: np.ndarray, reciprocal_one: np.ndarray,
                     reciprocal_two: np.ndarray, *, score_scale: float,
                     output_scale: float) -> dict[str, torch.Tensor]:
    """Evaluate the saved fused LUT path and same QK-score float references."""
    if score_scale <= 0 or output_scale <= 0 or scores.shape[-1] < 1:
        raise ValueError("positive scales and a nonempty score row are required")
    x = exact.integer(scores)
    s = list(map(int, scalars))
    if len(s) != 14 or len(exp_table) != 32 or len(reciprocal_one) != 64 or len(reciprocal_two) != 64:
        raise ValueError("invalid frozen Softmax ABI table shape")
    raw_minus = x.max(-1, keepdim=True).values - x
    minus = exact.wrap(raw_minus, 11)
    exp_codes = exact.address_lut(minus, s[:3], exp_table, 8, False)
    acc = exact.wrap(exp_codes.sum(-1), 23, False)
    one = exact.wrap((acc + s[3]) >> s[4], 9, False)
    two = exact.wrap((acc + s[8]) >> s[9], 7)
    use_two = one > s[5]
    recip_one = exact.wrap(exact.integer(reciprocal_one, x.device), 8, False)
    recip_two = exact.wrap(exact.integer(reciprocal_two, x.device), 8, False)
    recip_codes = torch.where(use_two, recip_two[two.clamp(0, s[10])],
                             recip_one[one.clamp(0, s[5])])
    lut_codes = exact.fused_softmax(x, scalars, exp_table, reciprocal_one, reciprocal_two)
    probability = torch.softmax(x.to(torch.float64) * score_scale, dim=-1)
    qmax = (1 << s[13]) - 1
    fp_codes = torch.round(probability / output_scale).clamp(0, qmax).to(torch.int64)
    exp_continuous = torch.exp(-raw_minus.to(torch.float64) * score_scale)
    exp_fp_codes = torch.round(exp_continuous * 4096).clamp(0, 65535).to(torch.int64)
    shift = torch.where(use_two, s[12], s[7])
    recip_fp_codes = torch.round(torch.pow(2.0, shift.to(torch.float64)) /
                                 (acc.clamp_min(1).to(torch.float64) * output_scale))
    recip_fp_codes = recip_fp_codes.clamp(0, 255).to(torch.int64)
    return dict(lut_codes=lut_codes, fp_codes=fp_codes, probability=probability,
                exp_lut_codes=exp_codes, exp_fp_codes=exp_fp_codes,
                exp_continuous=exp_continuous, recip_lut_codes=recip_codes,
                recip_fp_codes=recip_fp_codes, minus_wrap_count=(raw_minus != minus).sum(),
                zero_acc_count=(acc == 0).sum(), branch_two_count=use_two.sum(),
                row_count=torch.tensor(use_two.numel()),
                reference_clip_count=(torch.round(probability / output_scale) > qmax).sum())


def gelu_reference(q: torch.Tensor, input_scale: float, output_scale: float,
                   dataset: str) -> tuple[torch.Tensor, torch.Tensor]:
    if dataset == "imagenet":
        value = q.to(torch.float64) * input_scale
        real = 0.5 * value * (1 + torch.erf(value / math.sqrt(2)))
    else:
        value = q.to(torch.float32) * input_scale
        real = torch.nn.functional.gelu(value).to(torch.float64)
    return torch.round(real / output_scale).clamp(0, 7).to(torch.int64), real


def read_parameters(dataset: str, adapter) -> tuple[list[dict], dict[str, str]]:
    provenance = {}
    if dataset == "imagenet":
        base = ROOT / "image1k_hls_s3_original"
        metadata_path = base / "metadata/attention_qat_checkpoint.json"
        metadata = json.loads(metadata_path.read_text())
        exact_manifest_path = base / "exact/main/manifest.json"
        exact_manifest = json.loads(exact_manifest_path.read_text())
        artifact = adapter.artifact
        expected = metadata["best_formal"]["checkpoint_sha256"]
        if expected != exact_manifest["metadata"]["checkpoint_sha256"]:
            raise ValueError("ImageNet checkpoint and artifact identities differ")
        provenance[str(metadata_path)] = file_hash(metadata_path)
        provenance[str(exact_manifest_path)] = file_hash(exact_manifest_path)
        parameters = []
        selected = metadata["selected_activation_scales"]
        for block in range(12):
            p = artifact["blocks"][block]
            score_scale = float(selected["q"][block]) * float(selected["k"][block]) / 8
            output_scale = float(p["softmax"]["output_scale"])
            if not math.isclose(output_scale, float(selected["softmax"][block]), rel_tol=1e-5):
                raise ValueError(f"block{block:02d} ImageNet Softmax scale binding differs")
            parameters.append(dict(softmax=p["softmax"], score_scale=score_scale,
                                   gelu_scalars=p["gelu_lut"]["scalars"],
                                   gelu_table=p["gelu_lut"]["table"],
                                   gelu_input_scale=float(exact_manifest["metadata"]["blocks"][block]["physical_m1_scale"]),
                                   gelu_output_scale=float(selected["gelu"][block])))
        provenance[str(base / "exact/main/arrays.npz")] = file_hash(base / "exact/main/arrays.npz")
        return parameters, provenance
    if dataset == "plantvillage":
        base = ROOT / "quantization_final"
        stage4l = base / "artifacts/stage4l_exact_softmax_aq"
        gelu = base / "artifacts/stage4f_exact_gelu"
        reports = base / "reports"
    else:
        base = ROOT / "archive/nwpu_resisc45_ffvit/runs/nwpu_seed20260923"
        stage4l = base / "stage4l_exact_softmax_aq"
        gelu = base / "stage4f_exact_gelu"
        reports = base
    softmax_report_path = reports / "stage4l_exact_softmax_aq/report.json"
    gelu_report_path = reports / "stage4f_exact_gelu/report.json"
    softmax_report = json.loads(softmax_report_path.read_text())
    gelu_report = json.loads(gelu_report_path.read_text())
    softmax_scalars = np.load(stage4l / "softmax_scalars.npy", allow_pickle=False)
    exp_table = np.load(stage4l / "softmax_exp_table.npy", allow_pickle=False)
    recip_one = np.load(stage4l / "softmax_recip_table_one.npy", allow_pickle=False)
    recip_two = np.load(stage4l / "softmax_recip_table_two_int8.npy", allow_pickle=False)
    gelu_scalars = np.load(gelu / "ge_scalars.npy", allow_pickle=False)
    gelu_table = np.load(gelu / "ge_table.npy", allow_pickle=False)
    paths = [softmax_report_path, gelu_report_path]
    paths += [stage4l / name for name in ("softmax_scalars.npy", "softmax_exp_table.npy",
                                         "softmax_recip_table_one.npy", "softmax_recip_table_two_int8.npy")]
    paths += [gelu / name for name in ("ge_scalars.npy", "ge_table.npy")]
    provenance.update({str(path): file_hash(path) for path in paths})
    parameters = []
    for block in range(12):
        sm = softmax_report["blocks"][str(block)]
        ge = gelu_report["blocks"][str(block)]
        assert np.array_equal(exp_table[block], sm["exp"]["table"])
        assert np.array_equal(gelu_table[block], ge["table"])
        parameters.append(dict(softmax=dict(scalars=softmax_scalars[block],
                                             exp=exp_table[block], recip1=recip_one[block],
                                             recip2=recip_two[block]),
                               score_scale=float(sm["q_scale"]) * float(sm["k_scale"]) * float(sm["attn_scale"]),
                               gelu_scalars=gelu_scalars[block], gelu_table=gelu_table[block],
                               gelu_input_scale=float(ge["m1_int11_scale"]),
                               gelu_output_scale=float(ge["gelu_uint3_scale"])))
        if int(softmax_scalars[block, 13]) != int(softmax_report["clamp_bits"]):
            raise ValueError("Softmax probability clamp differs from saved report")
    return parameters, provenance


class UnitAudit:
    def __init__(self, dataset: str, parameters: list[dict]):
        self.dataset, self.parameters = dataset, parameters
        self.soft = [[CodeMoments(), CodeMoments(), CodeMoments()] for _ in range(12)]
        self.soft_real = [[RealMoments(), RealMoments()] for _ in range(12)]
        self.gelu_hist = [torch.zeros(2048, dtype=torch.int64) for _ in range(12)]
        self.soft_extra = [dict(minus_wrap_count=0, zero_acc_count=0, branch_two_count=0,
                                row_count=0, reference_clip_count=0) for _ in range(12)]
        self.soft_calls = [0] * 12
        self.gelu_calls = [0] * 12

    def softmax(self, block: int, scores: torch.Tensor) -> None:
        p = self.parameters[block]
        sm = p["softmax"]
        values = evaluate_softmax(scores, sm["scalars"], sm["exp"], sm["recip1"], sm["recip2"],
                                  score_scale=p["score_scale"], output_scale=float(sm.get("output_scale", 0) or
                                      (1 / 256)))
        self.soft[block][0].add(values["lut_codes"], values["fp_codes"])
        self.soft[block][1].add(values["exp_lut_codes"], values["exp_fp_codes"])
        self.soft[block][2].add(values["recip_lut_codes"], values["recip_fp_codes"])
        output_scale = float(sm.get("output_scale", 0) or (1 / 256))
        self.soft_real[block][0].add(values["lut_codes"] * output_scale, values["probability"])
        self.soft_real[block][1].add(values["exp_lut_codes"] / 4096, values["exp_continuous"])
        for key in self.soft_extra[block]:
            self.soft_extra[block][key] += int(values[key])
        self.soft_calls[block] += 1

    def gelu(self, block: int, codes: torch.Tensor) -> None:
        codes = codes.to(torch.int64)
        if bool(((codes < -1024) | (codes > 1023)).any()):
            raise ValueError(f"block{block:02d} GELU input escaped S11")
        self.gelu_hist[block] += torch.bincount((codes + 1024).reshape(-1), minlength=2048)
        self.gelu_calls[block] += 1

    def rows(self, image_count: int) -> list[dict]:
        rows = []
        for block in range(12):
            if self.soft_calls[block] != image_count or self.gelu_calls[block] != image_count:
                raise ValueError(f"block{block:02d} incomplete capture: Softmax {self.soft_calls[block]}, GELU {self.gelu_calls[block]}")
            p = self.parameters[block]
            sm = p["softmax"]
            for operator, metric, real in zip(("Softmax", "Softmax_EXP", "Softmax_Reciprocal"),
                                              self.soft[block], [self.soft_real[block][0], self.soft_real[block][1], None]):
                row = dict(dataset=self.dataset, instance=f"block{block:02d}", operator=operator,
                           input_images=image_count, method="FRESH_SOFTWARE_128" if image_count == 128 else "FRESH_SOFTWARE",
                           score_scale=p["score_scale"], output_scale=float(sm.get("output_scale", 0) or (1 / 256)),
                           **metric.result())
                row.update(real.result() if real is not None else
                           dict(real_mae="NOT_MEASURED", real_rmse="NOT_MEASURED", real_max_ae="NOT_MEASURED"))
                row.update(self.soft_extra[block])
                rows.append(row)
            q = torch.arange(-1024, 1024, dtype=torch.int64)
            bias, shift, bound = map(int, p["gelu_scalars"][:3])
            table = exact.integer(p["gelu_table"])
            if len(table) != 64:
                raise ValueError("GELU table must have 64 entries")
            prediction = table[((q + bias) >> shift).clamp(0, bound)]
            reference, real = gelu_reference(q, p["gelu_input_scale"], p["gelu_output_scale"], self.dataset)
            code = CodeMoments()
            code.add_histogram(prediction, reference, self.gelu_hist[block])
            physical = RealMoments()
            physical.add_histogram(prediction * p["gelu_output_scale"], real, self.gelu_hist[block])
            rows.append(dict(dataset=self.dataset, instance=f"block{block:02d}", operator="GELU",
                             input_images=image_count, method="FRESH_SOFTWARE_128" if image_count == 128 else "FRESH_SOFTWARE",
                             input_scale=p["gelu_input_scale"], output_scale=p["gelu_output_scale"],
                             **code.result(), **physical.result()))
        return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run_dataset(dataset: str, sample_count: int, output: Path) -> None:
    import capture_ln
    from capture_ln import Adapter
    capture_ln.HERE = HERE  # Route its per-process caches and copies into this validation directory.
    source = ROOT / "validation/ln_iotj_20261008/outputs/final128" / dataset / "samples.json"
    historical = json.loads(source.read_text())["samples"]
    # PyTorch registers synthetic relative ``torch.ops``/``torch.classes``
    # __file__ names.  The legacy adapter hashes imported project sources;
    # resolve those synthetic names inside its excluded validation directory.
    previous_cwd = Path.cwd()
    try:
        os.chdir(HERE)
        adapter = Adapter(dataset, output, sample_count)
    finally:
        os.chdir(previous_cwd)
    if sample_count == 128 and [int(item["index"]) for item in historical] != adapter.indices:
        raise ValueError("the historical LN 128-image selection differs")
    parameters, provenance = read_parameters(dataset, adapter)
    audit = UnitAudit(dataset, parameters)
    captures = []
    if dataset == "imagenet":
        original = adapter.exact.block_forward
        block_cursor = [0]
        def block_with_audit(x, p, *, trace=False):
            block = block_cursor[0] % 12
            output_value, values = original(x, p, trace=True)
            audit.softmax(block, values["scores"])
            audit.gelu(block, values["m1_raw"])
            block_cursor[0] += 1
            return output_value, values
        adapter.exact.block_forward = block_with_audit
    else:
        blocks = adapter.model.qat_model.vit.blocks
        report_path = (ROOT / "quantization_final/reports/stage4l_exact_softmax_aq/report.json"
                       if dataset == "plantvillage" else
                       ROOT / "archive/nwpu_resisc45_ffvit/runs/nwpu_seed20260923/stage4l_exact_softmax_aq/report.json")
        fit = json.loads(report_path.read_text())["blocks"]
        for block in range(12):
            scales = fit[str(block)]
            def qkv_hook(module, inputs, value, block=block, scales=scales):
                q_values, k_values, _ = value.chunk(3, dim=-1)
                q = torch.round(q_values / float(scales["q_scale"])).to(torch.int64)
                k = torch.round(k_values / float(scales["k_scale"])).to(torch.int64)
                if not torch.allclose(q_values, q * float(scales["q_scale"]), atol=1e-5, rtol=1e-5):
                    raise ValueError("Q real/code binding differs from saved fitted scale")
                if not torch.allclose(k_values, k * float(scales["k_scale"]), atol=1e-5, rtol=1e-5):
                    raise ValueError("K real/code binding differs from saved fitted scale")
                if bool(((q < -4) | (q > 3) | (k < -4) | (k > 3)).any()):
                    raise ValueError("Q/K output escaped signed3")
                q = q.reshape(1, 196, 3, 64).permute(0, 2, 1, 3)
                k = k.reshape(1, 196, 3, 64).permute(0, 2, 1, 3)
                audit.softmax(block, exact.matmul(q, k.transpose(-1, -2)))
            def gelu_hook(module, inputs, block=block):
                input_scale = parameters[block]["gelu_input_scale"]
                q = torch.round(inputs[0] / input_scale).to(torch.int64)
                if not torch.allclose(inputs[0], q * input_scale, atol=1e-5, rtol=1e-5):
                    raise ValueError("GELU real/code binding differs from saved fitted scale")
                audit.gelu(block, q)
            captures.append(blocks[block].attn.qkv.register_forward_hook(qkv_hook))
            captures.append(blocks[block].mlp.act.register_forward_pre_hook(gelu_hook))
    try:
        adapter.run(lambda *_: None)
    finally:
        for handle in captures:
            handle.remove()
    if len(adapter.records) != sample_count:
        raise ValueError("incomplete image execution")
    if sample_count == 128:
        for actual, expected in zip(adapter.records, historical):
            if (actual["index"] != expected["index"] or
                actual["source_image_sha256"] != expected["source_image_sha256"] or
                actual["transformed_fp32_sha256"] != expected["transformed_fp32_sha256"]):
                raise ValueError("natural sample identity differs from historical LN run")
    rows = audit.rows(sample_count)
    write_csv(output / "unit_accuracy.csv", rows)
    np.savez_compressed(output / "gelu_input_histograms.npz",
                        **{f"block{block:02d}": value.numpy() for block, value in enumerate(audit.gelu_hist)})
    (output / "samples.json").write_text(json.dumps(adapter.records, indent=2) + "\n")
    manifest = dict(dataset=dataset, method="SOFTWARE_SAME_INPUT_EXPORTED_LUT",
                    sample_count=sample_count, tokens_per_image=196,
                    per_block_softmax_rows=sample_count * 3 * 196,
                    per_block_softmax_output_codes=sample_count * 3 * 196 * 196,
                    per_block_gelu_input_codes=sample_count * 196 * 768,
                    source_hashes=provenance,
                    historical_ln_samples=str(source), historical_ln_samples_sha256=file_hash(source),
                    numeric_source=str(Path(__file__).resolve()), numeric_source_sha256=file_hash(Path(__file__)),
                    execution=dict(csim="NOT_MEASURED", rtl_cosim="NOT_MEASURED", fpga="NOT_MEASURED"))
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(dict(dataset=dataset, images=sample_count, unit_rows=len(rows), status="COMPLETE")))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=("plantvillage", "nwpu", "imagenet"), required=True)
    parser.add_argument("--samples", type=int, default=128)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = (args.output or HERE / "outputs" / args.dataset).resolve()
    if not output.is_relative_to(HERE) or output == HERE:
        raise ValueError("output must stay under independent validation directory")
    output.mkdir(parents=True, exist_ok=True)
    run_dataset(args.dataset, args.samples, output)


if __name__ == "__main__":
    main()
