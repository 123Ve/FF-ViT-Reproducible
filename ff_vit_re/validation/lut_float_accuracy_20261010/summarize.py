"""Build count-weighted, source-linked summaries of the independent LUT audit."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATASETS = ("plantvillage", "nwpu", "imagenet")
LABELS = {"plantvillage": "PlantVillage", "nwpu": "NWPU-RESISC45", "imagenet": "ImageNet-1K S3"}


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source))


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def digest(path: Path) -> str:
    hash_value = hashlib.sha256()
    with path.open("rb") as source:
        for part in iter(lambda: source.read(1024 * 1024), b""):
            hash_value.update(part)
    return hash_value.hexdigest()


def aggregate(rows: list[dict]) -> dict:
    if not rows:
        raise ValueError("cannot aggregate empty rows")
    count = sum(int(row["count"]) for row in rows)
    if count == 0:
        raise ValueError("cannot aggregate zero-count rows")
    result = dict(count=count,
                  mae_lsb=sum(int(row["count"]) * float(row["mae_lsb"]) for row in rows) / count,
                  rmse_lsb=math.sqrt(sum(int(row["count"]) * float(row["rmse_lsb"]) ** 2 for row in rows) / count),
                  max_ae_lsb=max(int(row["max_ae_lsb"]) for row in rows),
                  exact_rate=sum(int(row["count"]) * float(row["exact_rate"]) for row in rows) / count,
                  within_1_lsb_rate=sum(int(row["count"]) * float(row["within_1_lsb_rate"]) for row in rows) / count)
    if all(row.get("real_mae") not in (None, "", "NOT_MEASURED", "MISSING") for row in rows):
        result.update(real_mae=sum(int(row["count"]) * float(row["real_mae"]) for row in rows) / count,
                      real_rmse=math.sqrt(sum(int(row["count"]) * float(row["real_rmse"]) ** 2 for row in rows) / count),
                      real_max_ae=max(float(row["real_max_ae"]) for row in rows))
    else:
        result.update(real_mae="NOT_MEASURED", real_rmse="NOT_MEASURED", real_max_ae="NOT_MEASURED")
    return result


def main() -> None:
    global_rows, ln_rows, rsqrt_rows, exhaustive_rows = [], [], [], []
    checks = {}
    prior_path = ROOT / "validation/ffvit_review_evidence_20261009/nonlinear_error.csv"
    prior = read_csv(prior_path)
    ln_root = ROOT / "validation/ln_iotj_20261008/outputs/final128"
    for dataset in DATASETS:
        fresh_dir = HERE / "outputs" / dataset
        fresh_path = fresh_dir / "unit_accuracy.csv"
        fresh = read_csv(fresh_path)
        manifest = json.loads((fresh_dir / "manifest.json").read_text())
        current_samples = json.loads((fresh_dir / "samples.json").read_text())
        old_dir = ln_root / dataset
        previous_samples = json.loads((old_dir / "samples.json").read_text())["samples"]
        if manifest["sample_count"] != 128 or len(current_samples) != len(previous_samples) != 128:
            raise ValueError(f"{dataset}: not 128 matched images")
        for a, b in zip(current_samples, previous_samples):
            for key in ("index", "source_image_sha256", "transformed_fp32_sha256"):
                if a[key] != b[key]:
                    raise ValueError(f"{dataset}: sample mismatch at index {a['index']} ({key})")
        if len(fresh) != 48:
            raise ValueError(f"{dataset}: expected 48 fresh per-block rows, found {len(fresh)}")
        for operator, expected_count in (("Softmax", 128 * 3 * 196 * 196),
                                         ("Softmax_EXP", 128 * 3 * 196 * 196),
                                         ("Softmax_Reciprocal", 128 * 3 * 196),
                                         ("GELU", 128 * 196 * 768)):
            selected = [row for row in fresh if row["operator"] == operator]
            if len(selected) != 12 or len({row["instance"] for row in selected}) != 12:
                raise ValueError(f"{dataset} {operator}: incomplete block coverage")
            if any(int(row["count"]) != expected_count for row in selected):
                raise ValueError(f"{dataset} {operator}: incomplete element coverage")
            global_rows.append(dict(dataset=dataset, operator=operator, scope="128_IMAGE_NATURAL",
                                    error_unit="output LSB" if operator in ("Softmax", "GELU") else
                                    ("exp table code (1/4096)" if operator == "Softmax_EXP" else "reciprocal table code"),
                                    source=f"{fresh_path}:operator={operator},12 blocks", **aggregate(selected)))
        old = json.loads((old_dir / "summary.json").read_text())
        if old["sample_count"] != 128 or len(old["instances"]) != 24:
            raise ValueError(f"{dataset}: incomplete prior LayerNorm audit")
        for instance in old["instances"]:
            output = instance["e07_vs_fp32_quantized"]
            attrib = instance["attribution"]["lut_rsqrt"]
            ln_rows.append(dict(dataset=dataset, instance=instance["name"], count=output["count"],
                                mae_lsb=output["code_mae"], rmse_lsb=output["code_rmse"],
                                max_ae_lsb=output["code_maxae"], exact_rate=output["exact_code_agreement"],
                                within_1_lsb_rate=output["within_1_lsb"], input_scale=instance["input_scale"],
                                output_scale=instance["output_scale"],
                                source=f"{old_dir / 'summary.json'}:instances[name={instance['name']}].e07_vs_fp32_quantized"))
            rsqrt_rows.append(dict(dataset=dataset, instance=instance["name"], count=attrib["count"],
                                   mae=attrib["mae"], rmse=attrib["rmse"], max_ae=attrib["maxae"],
                                   unit="inverse input-code", source=f"{old_dir / 'summary.json'}:instances[name={instance['name']}].attribution.lut_rsqrt"))
        ln_selected = [row for row in ln_rows if row["dataset"] == dataset]
        ln_aggregate = aggregate(ln_selected)
        direct = old["global_metrics"]["e07_vs_fp32_quantized"]
        if ln_aggregate["count"] != direct["count"] or not math.isclose(ln_aggregate["mae_lsb"], direct["code_mae"], abs_tol=1e-12):
            raise ValueError(f"{dataset}: per-instance/global LN inconsistency")
        ln_aggregate.update(real_mae="NOT_COMPARABLE_ACROSS_SCALES", real_rmse="NOT_COMPARABLE_ACROSS_SCALES",
                            real_max_ae="NOT_COMPARABLE_ACROSS_SCALES")
        global_rows.append(dict(dataset=dataset, operator="LayerNorm_LN1_LN2", scope="128_IMAGE_NATURAL",
                                error_unit="output LSB", source=f"{old_dir / 'summary.json'}:global_metrics.e07_vs_fp32_quantized",
                                **ln_aggregate))
        rsqrt_selected = [row for row in rsqrt_rows if row["dataset"] == dataset]
        rsqrt_count = sum(int(row["count"]) for row in rsqrt_selected)
        global_rows.append(dict(dataset=dataset, operator="LayerNorm_Rsqrt", scope="128_IMAGE_NATURAL",
                                error_unit="inverse input-code", count=rsqrt_count,
                                mae_lsb="NOT_APPLICABLE", rmse_lsb="NOT_APPLICABLE", max_ae_lsb="NOT_APPLICABLE",
                                exact_rate="NOT_APPLICABLE", within_1_lsb_rate="NOT_APPLICABLE",
                                real_mae=sum(int(row["count"]) * float(row["mae"]) for row in rsqrt_selected) / rsqrt_count,
                                real_rmse=math.sqrt(sum(int(row["count"]) * float(row["rmse"]) ** 2 for row in rsqrt_selected) / rsqrt_count),
                                real_max_ae=max(float(row["max_ae"]) for row in rsqrt_selected),
                                source=f"{old_dir / 'summary.json'}:instances[*].attribution.lut_rsqrt"))
        previous_gelu = [row for row in prior if row["dataset"] == dataset and row["operator"] == "GELU"
                         and row["scope"] == "EXHAUSTIVE_S11_2048"]
        if len(previous_gelu) != 12 or any(int(row["count"]) != 2048 for row in previous_gelu):
            raise ValueError(f"{dataset}: prior exhaustive GELU coverage missing")
        for row in previous_gelu:
            exhaustive_rows.append(dict(dataset=dataset, instance=row["instance"], count=row["count"],
                                        mae_lsb=row["mae"], rmse_lsb=row["rmse"], max_ae_lsb=row["max_abs_error"],
                                        exact_rate=row["exact_code_agreement"], within_1_lsb_rate=row["within_1_lsb"],
                                        source=row["source"]))
        global_rows.append(dict(dataset=dataset, operator="GELU", scope="EXHAUSTIVE_S11_2048",
                                error_unit="output LSB", source=f"{prior_path}:GELU,EXHAUSTIVE_S11_2048,12 blocks",
                                **aggregate([row for row in exhaustive_rows if row["dataset"] == dataset])))
        checks[dataset] = dict(sample_match=True, fresh_rows=len(fresh), ln_instances=len(ln_selected),
                               GELU_exhaustive_codes=12 * 2048,
                               fresh_sha256=digest(fresh_path), ln_sha256=digest(old_dir / "summary.json"),
                               sample_sha256=digest(fresh_dir / "samples.json"))
    write_csv(HERE / "global_unit_accuracy.csv", global_rows)
    write_csv(HERE / "ln_per_instance.csv", ln_rows)
    write_csv(HERE / "rsqrt_per_instance.csv", rsqrt_rows)
    write_csv(HERE / "gelu_exhaustive_per_block.csv", exhaustive_rows)
    (HERE / "summary_checks.json").write_text(json.dumps(checks, indent=2) + "\n")
    lines = [r"\begin{table*}[t]", r"\centering", r"\caption{Software-only LUT-unit accuracy against same-input floating-point references on 128 deterministic images per dataset. MAE and MaxAE are in each unit's output LSB; exact and $\leq1$ denote output-code agreement.}",
             r"\label{tab:lut_float_accuracy}", r"\begin{tabular}{llrrrr}", r"\toprule",
             r"Dataset & Unit & MAE (LSB) & MaxAE (LSB) & Exact (\%) & $\leq1$ LSB (\%) \\", r"\midrule"]
    for dataset in DATASETS:
        for operator, label in (("Softmax", "Softmax"), ("LayerNorm_LN1_LN2", "LayerNorm"), ("GELU", "GELU")):
            row = next(row for row in global_rows if row["dataset"] == dataset and row["operator"] == operator
                       and row["scope"] == "128_IMAGE_NATURAL")
            lines.append(f"{LABELS[dataset]} & {label} & {float(row['mae_lsb']):.4f} & {int(row['max_ae_lsb'])} & "
                         f"{100 * float(row['exact_rate']):.3f} & {100 * float(row['within_1_lsb_rate']):.3f} " + r"\\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table*}"]
    (HERE / "lut_accuracy_table.tex").write_text("\n".join(lines) + "\n")
    print(json.dumps(dict(status="COMPLETE", datasets=list(DATASETS), summary_rows=len(global_rows),
                          per_instance_ln_rows=len(ln_rows), per_instance_rsqrt_rows=len(rsqrt_rows))))


if __name__ == "__main__":
    main()
