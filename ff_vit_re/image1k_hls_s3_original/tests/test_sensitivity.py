import csv
import json
import math
import subprocess
import sys

import pytest
import torch
from torch import nn

from src.sensitivity import (
    aggregate_probe_shards,
    aggregate_shards,
    enumerate_experiments,
    evaluate_experiment,
    experiment_sha256,
    load_compatible_shard,
    write_shard,
)


HASHES = {"config_sha256": "a" * 64, "checkpoint_sha256": "b" * 64,
          "data_sha256": "c" * 64, "scales_sha256": "d" * 64}


def test_enumeration_covers_operator_groups_layers_and_both_cumulative_orders():
    experiments = enumerate_experiments(12, low_sensitivity_order=(2, 0, 1, *range(3, 12)))
    by_id = {item.id: item for item in experiments}
    assert len(by_id) == len(experiments) == 77
    assert {name.removeprefix("operator-") for name in by_id if name.startswith("operator-")} == {
        "ln1", "q", "k", "v", "a", "softmax", "ln2", "gelu",
        "fc1_weight", "fc2_weight", "attention_residual", "mlp_residual",
    }
    assert {name for name in by_id if name.startswith("group-")} == {
        "group-qkv", "group-attention-all", "group-mlp-all", "group-all-a3",
    }
    assert set(by_id["group-qkv"].masks) == {"q", "k", "v"}
    assert set(by_id["group-attention-all"].masks) == {"ln1", "q", "k", "v", "a"}
    assert set(by_id["group-mlp-all"].masks) == {"ln2", "gelu"}
    assert set(by_id["group-all-a3"].masks) == {
        "ln1", "q", "k", "v", "a", "ln2", "gelu", "mlp_residual",
    }
    assert sum(name.startswith("layer-") for name in by_id) == 36
    assert by_id["layer-03-attention"].masks["q"] == (3,)
    assert by_id["layer-03-mlp"].masks["gelu"] == (3,)
    assert by_id["layer-03-whole-block"].masks["q"] == (3,)
    assert by_id["layer-03-whole-block"].masks["gelu"] == (3,)
    assert by_id["cumulative-low-01"].masks["q"] == (2,)
    assert by_id["cumulative-low-02"].masks["q"] == (2, 0)
    assert by_id["cumulative-rear-02"].masks["q"] == (11, 10)
    assert by_id["baseline"].masks == {}


def test_enumeration_rejects_incomplete_or_duplicate_ranking():
    with pytest.raises(ValueError, match="permutation"):
        enumerate_experiments(12, low_sensitivity_order=(0,) * 12)


@pytest.mark.parametrize("changed", ["config_sha256", "checkpoint_sha256", "data_sha256", "scales_sha256", "sample_count"])
def test_resume_rejects_any_incompatible_identity(tmp_path, changed):
    path = tmp_path / "baseline.json"
    experiment = enumerate_experiments(1, low_sensitivity_order=(0,))[0]
    shard = {"schema_version": 1, "experiment_id": "baseline",
             "experiment_sha256": experiment_sha256(experiment), **HASHES,
             "sample_count": 2, "top1": 0.5, "top5": 1.0, "duration_seconds": 1.0,
             "device": "cpu", "tensor_metrics": {}}
    write_shard(path, shard)
    expected = {**HASHES, "sample_count": 2}
    expected[changed] = 3 if changed == "sample_count" else "e" * 64
    with pytest.raises(ValueError, match=changed):
        load_compatible_shard(path, experiment_id="baseline", expected=expected,
                              experiment=experiment)
    assert json.loads(path.read_text()) == shard


class SmallModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.vit = nn.Module()
        self.vit.blocks = nn.Sequential(Block())
        self.head = nn.Linear(3, 5, bias=False)
        with torch.no_grad():
            self.head.weight.copy_(torch.eye(5, 3))

    def forward(self, x):
        return self.head(self.vit.blocks(x).mean(dim=1))


class Attention(nn.Module):
    def __init__(self):
        super().__init__()
        self.num_heads, self.head_dim, self.scale = 1, 3, 3 ** -.5
        self.qkv = nn.Linear(3, 9, bias=False)
        self.q_norm = self.k_norm = self.attn_drop = self.norm = self.proj_drop = nn.Identity()
        self.proj = nn.Linear(3, 3, bias=False)

    def forward(self, x, attn_mask=None):
        batch, tokens, channels = x.shape
        q, k, v = self.qkv(x).reshape(batch, tokens, 3, 1, 3).permute(2, 0, 3, 1, 4).unbind(0)
        a = (q * self.scale @ k.transpose(-2, -1)).softmax(-1)
        return self.proj((a @ v).transpose(1, 2).reshape(batch, tokens, channels))


class Block(nn.Module):
    def __init__(self):
        super().__init__()
        self.norm1 = nn.Identity()
        self.norm2 = nn.Identity()
        self.attn = Attention()
        self.mlp = nn.Module()
        self.mlp.fc1 = nn.Linear(3, 3)
        self.mlp.act = nn.GELU()
        self.mlp.fc2 = nn.Linear(3, 3)

    def forward(self, x):
        x = x + self.attn(self.norm1(x))
        return x + self.mlp.fc2(self.mlp.act(self.mlp.fc1(self.norm2(x))))


class TinyW3Linear(nn.Linear):
    def __init__(self):
        super().__init__(3, 3, bias=False)
        self.segments = (3,)
        self.quant_enabled = True
        with torch.no_grad():
            self.weight.copy_(torch.arange(9, dtype=torch.float32).reshape(3, 3))

    def set_quant_enabled(self, enabled):
        self.quant_enabled = bool(enabled)

    def scales(self):
        return torch.ones(1)

    def fake_quant_weight(self):
        return self.weight.round().clamp(-4, 3)

    def forward(self, x):
        return nn.functional.linear(x, self.fake_quant_weight() if self.quant_enabled else self.weight)


def test_evaluation_counts_unique_samples_and_aggregates_tensor_error():
    from src.quant import StrictS3Controller

    torch.manual_seed(3)
    model = SmallModel().eval()
    controller = StrictS3Controller(model, scales={"ln1": [0.3]})
    experiment = enumerate_experiments(1, low_sensitivity_order=(0,))[1]
    assert experiment.id == "operator-ln1"
    loader = [(torch.rand(2, 2, 3), torch.tensor([0, 1]), ["a", "b"]),
              (torch.rand(1, 2, 3), torch.tensor([2]), ["c"])]
    shard = evaluate_experiment(model, controller, loader, experiment,
                                expected={**HASHES, "sample_count": 3}, device="cpu")
    assert shard["sample_count"] == 3
    assert 0 <= shard["top1"] <= shard["top5"] <= 1
    assert shard["tensor_metrics"]["0:ln1"]["mse"] >= 0
    assert shard["tensor_metrics"]["0:ln1"]["elements"] == 18
    assert controller.observations == {}


@pytest.mark.parametrize("weight_operator", ["fc1_weight", "fc2_weight"])
def test_weight_only_metrics_cover_exact_selected_block_and_operator(weight_operator):
    from src.quant import StrictS3Controller
    from src.sensitivity import Experiment

    model = SmallModel().eval()
    model.vit.blocks = nn.Sequential(Block(), Block())
    for block in model.vit.blocks:
        block.mlp.fc1 = TinyW3Linear()
        block.mlp.fc2 = TinyW3Linear()
    controller = StrictS3Controller(model, scales={})
    experiment = Experiment(f"{weight_operator}-block-0", "operator", {weight_operator: (0,)})
    shard = evaluate_experiment(model, controller,
                                [(torch.ones(1, 2, 3), torch.tensor([0]), ["one"])],
                                experiment, expected={**HASHES, "sample_count": 1}, device="cpu")
    assert set(shard["tensor_metrics"]) == {f"0:{weight_operator}"}
    metrics = shard["tensor_metrics"][f"0:{weight_operator}"]
    assert metrics["elements"] == 9
    assert metrics["mse"] == pytest.approx(55 / 9)
    assert metrics["mae"] == pytest.approx(15 / 9)
    assert metrics["clip_rate"] == pytest.approx(5 / 9)
    assert metrics["zero_rate"] == pytest.approx(1 / 9)
    assert metrics["observed_min"] == 0
    assert metrics["observed_max"] == 8
    assert metrics["cosine"] == pytest.approx(104 / (math.sqrt(204) * math.sqrt(59)))
    assert metrics["sqnr_db"] == pytest.approx(10 * math.log10(204 / 55))
    assert all(block.mlp.fc1.quant_enabled for block in model.vit.blocks)


def test_dataset_cosine_uses_global_dot_and_norms_across_batches():
    from src.quant import StrictS3Controller

    model = SmallModel().eval()
    controller = StrictS3Controller(model, scales={"ln1": [1.]})
    experiment = enumerate_experiments(1, low_sensitivity_order=(0,))[1]
    loader = [(torch.tensor([[[1., 0., 0.]]]), torch.tensor([0]), ["a"]),
              (torch.tensor([[[.4, .4, 0.]]]), torch.tensor([0]), ["b"])]
    shard = evaluate_experiment(model, controller, loader, experiment,
                                expected={**HASHES, "sample_count": 2}, device="cpu")
    metrics = shard["tensor_metrics"]["0:ln1"]
    assert metrics["cosine"] == pytest.approx(1 / math.sqrt(1.32), rel=1e-6)
    assert metrics["mse"] == pytest.approx(.32 / 6)
    assert metrics["mae"] == pytest.approx(.8 / 6)
    assert metrics["zero_rate"] == pytest.approx(5 / 6)
    assert metrics["clip_rate"] == 0


def test_evaluation_rejects_duplicate_ids_and_wrong_count():
    from src.quant import StrictS3Controller

    model = SmallModel().eval()
    controller = StrictS3Controller(model, scales={})
    experiment = enumerate_experiments(1, low_sensitivity_order=(0,))[0]
    loader = [(torch.rand(2, 2, 3), torch.tensor([0, 1]), ["a", "a"])]
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_experiment(model, controller, loader, experiment,
                            expected={**HASHES, "sample_count": 2}, device="cpu")


def test_resume_rejects_changed_cumulative_masks_even_with_same_id(tmp_path):
    first = enumerate_experiments(2, low_sensitivity_order=(0, 1))[-4]
    changed = enumerate_experiments(2, low_sensitivity_order=(1, 0))[-4]
    assert first.id == changed.id == "cumulative-low-01"
    assert experiment_sha256(first) != experiment_sha256(changed)
    path = tmp_path / "cumulative-low-01.json"
    write_shard(path, {"schema_version": 1, "experiment_id": first.id,
                       "experiment_sha256": experiment_sha256(first), **HASHES,
                       "sample_count": 2, "top1": 0.5, "top5": 1.0,
                       "tensor_metrics": {}})
    with pytest.raises(ValueError, match="experiment_sha256"):
        load_compatible_shard(path, experiment_id=changed.id,
                              expected={**HASHES, "sample_count": 2}, experiment=changed)


def test_resume_rejects_missing_weight_metrics(tmp_path):
    experiment = next(case for case in enumerate_experiments(1, low_sensitivity_order=(0,))
                      if case.id == "operator-fc1_weight")
    path = tmp_path / "operator-fc1_weight.json"
    write_shard(path, {"schema_version": 1, "experiment_id": experiment.id,
                       "experiment_sha256": experiment_sha256(experiment), **HASHES,
                       "sample_count": 2, "top1": 0.5, "top5": 1.0,
                       "tensor_metrics": {}})
    with pytest.raises(ValueError, match="tensor_metrics"):
        load_compatible_shard(path, experiment_id=experiment.id,
                              expected={**HASHES, "sample_count": 2}, experiment=experiment)
    with pytest.raises((TypeError, ValueError)):
        load_compatible_shard(path, experiment_id=experiment.id,
                              expected={**HASHES, "sample_count": 2})


def test_zero_error_tensor_metrics_serialize_as_strict_json():
    from src.quant import StrictS3Controller

    model = SmallModel().eval()
    controller = StrictS3Controller(model, scales={"ln1": [1.0]})
    experiment = enumerate_experiments(1, low_sensitivity_order=(0,))[1]
    shard = evaluate_experiment(model, controller,
                                [(torch.zeros(1, 2, 3), torch.tensor([0]), ["zero"])],
                                experiment, expected={**HASHES, "sample_count": 1}, device="cpu")
    json.dumps(shard, allow_nan=False)


@pytest.mark.parametrize("sample_count,aggregate,prefix", [
    (2, aggregate_probe_shards, "probe_"),
    (50_000, aggregate_shards, ""),
])
def test_aggregation_writes_stable_reports_and_drops(tmp_path, sample_count, aggregate, prefix):
    experiments = enumerate_experiments(1, low_sensitivity_order=(0,))
    shards = tmp_path / "shards"
    shards.mkdir()
    neutral_metric = {"elements": 1, "mse": 0.0, "mae": 0.0,
                      "cosine": 1.0, "sqnr_db": None, "clip_rate": 0.0,
                      "zero_rate": 0.0, "observed_min": 1.0, "observed_max": 1.0}
    for index, experiment in enumerate(experiments):
        write_shard(shards / f"{experiment.id}.json", {
            "schema_version": 1, "experiment_id": experiment.id,
            "experiment_sha256": experiment_sha256(experiment), **HASHES,
            "sample_count": sample_count, "top1": (2 - int(index != 0)) / 2,
            "top5": 1.0, "duration_seconds": 1.0, "device": "cpu",
            "tensor_metrics": {f"{block}:{name}": neutral_metric
                               for name, blocks in experiment.masks.items() for block in blocks},
        })
    reports = tmp_path / "reports"
    aggregate(shards, reports, experiments, expected={**HASHES, "sample_count": sample_count})
    first = (reports / f"{prefix}operator_sensitivity.json").read_bytes()
    aggregate(shards, reports, experiments, expected={**HASHES, "sample_count": sample_count})
    assert (reports / f"{prefix}operator_sensitivity.json").read_bytes() == first
    records = json.loads(first)["records"]
    assert records[1]["top1_drop_pp"] == 50.0
    operator_payload = json.loads(first)
    assert operator_payload["ranking"] == sorted(case.id for case in experiments
                                                 if case.family == "operator" and case.id != "baseline")
    header = (reports / f"{prefix}operator_sensitivity.csv").read_text().splitlines()[0]
    assert all(name in header for name in ("config_sha256", "checkpoint_sha256",
                                           "data_sha256", "scales_sha256", "experiment_sha256"))
    report_rows = {row["experiment_id"]: row for row in operator_payload["records"]}
    csv_rows = {row["experiment_id"]: row for row in csv.DictReader(
        (reports / f"{prefix}operator_sensitivity.csv").open(newline=""))}
    markdown = (reports / f"{prefix}operator_sensitivity.md").read_text()
    for experiment_id in ("operator-fc1_weight", "operator-fc2_weight"):
        assert report_rows[experiment_id]["perturbation_direction"] == "W3_to_FP32_removal_ablation"
        assert report_rows[experiment_id]["tensor_metric_direction"] == "FP32_master_to_W3_quantized"
        assert csv_rows[experiment_id]["perturbation_direction"] == "W3_to_FP32_removal_ablation"
        assert csv_rows[experiment_id]["tensor_metric_direction"] == "FP32_master_to_W3_quantized"
        assert f"| {experiment_id} | W3_to_FP32_removal_ablation | FP32_master_to_W3_quantized |" in markdown
    assert report_rows["baseline"]["perturbation_direction"] == "no_perturbation"
    assert report_rows["baseline"]["tensor_metric_direction"] == "not_applicable"
    assert report_rows["operator-ln1"]["perturbation_direction"] == "FP32_activation_to_strict_quantized"
    assert report_rows["operator-ln1"]["tensor_metric_direction"] == "FP32_activation_to_strict_quantized"
    assert (reports / f"{prefix}layer_sensitivity.csv").exists()
    assert (reports / f"{prefix}cumulative_sensitivity.md").exists()
    if prefix:
        assert not (reports / "operator_sensitivity.json").exists()


def test_formal_aggregation_rejects_probe_count_before_publication(tmp_path):
    with pytest.raises(ValueError, match="50,000"):
        aggregate_shards(tmp_path / "missing", tmp_path / "reports",
                         enumerate_experiments(1, low_sensitivity_order=(0,)),
                         expected={**HASHES, "sample_count": 2})
    assert not (tmp_path / "reports").exists()


def test_runner_lists_cases_without_loading_checkpoint(tmp_path):
    ranking = tmp_path / "ranking.json"
    ranking.write_text("[0]\n")
    result = subprocess.run(
        [sys.executable, "scripts/run_sensitivity.py", "--list", "--blocks", "1",
         "--ranking", str(ranking)], capture_output=True, text=True, check=True,
    )
    assert len(json.loads(result.stdout)) == 22
    assert "cumulative-low-01" in json.loads(result.stdout)
