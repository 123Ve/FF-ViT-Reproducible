from copy import deepcopy
from pathlib import Path

import pytest

from src.contract import load_contract, validate_mainline_contract


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config" / "original_hls_s3.yaml"


EXPECTED_WIDTHS = {
    "q_weight": ("signed", 3),
    "k_weight": ("signed", 3),
    "v_weight": ("signed", 3),
    "o_weight": ("signed", 3),
    "fc1_weight": ("signed", 3),
    "fc2_weight": ("signed", 3),
    "ln1_output": ("signed", 3),
    "q_output": ("signed", 3),
    "k_output": ("signed", 3),
    "v_output": ("signed", 3),
    "attention_a": ("signed", 3),
    "projection_input": ("signed", 3),
    "softmax_output": ("unsigned", 3),
    "ln2_output": ("signed", 3),
    "gelu_output": ("unsigned", 3),
    "attention_q_accumulator": ("signed", 12),
    "attention_k_accumulator": ("signed", 11),
    "attention_v_accumulator": ("signed", 11),
    "attention_r_accumulator": ("signed", 10),
    "attention_a_accumulator": ("signed", 11),
    "attention_o_accumulator": ("signed", 13),
    "attention_residual_output": ("signed", 15),
    "mlp1_accumulator": ("signed", 11),
    "mlp2_accumulator": ("signed", 13),
    "block_feature_map": ("signed", 13),
    "head_layernorm": ("signed", 8),
    "head_weight": ("signed", 8),
    "head_bias": ("signed", 19),
    "head_mac": ("signed", 19),
}


def _widths(config):
    return {
        name: (item["signedness"], item["bits"])
        for name, item in config["numeric_contract"].items()
    }


def test_load_contract_has_the_exact_original_hls_signedness_and_widths():
    config = load_contract(CONTRACT_PATH)

    assert _widths(config) == EXPECTED_WIDTHS
    validate_mainline_contract(config)


@pytest.mark.parametrize(
    ("boundary", "field", "replacement"),
    [
        ("gelu_output", "bits", 4),
        ("ln1_output", "bits", 4),
        ("ln2_output", "bits", 4),
        ("q_weight", "bits", 4),
    ],
)
def test_mainline_validator_rejects_widened_gelu_layernorm_and_weights(
    boundary, field, replacement
):
    config = load_contract(CONTRACT_PATH)
    config = deepcopy(config)
    config["numeric_contract"][boundary][field] = replacement

    with pytest.raises(ValueError, match="mainline numeric contract"):
        validate_mainline_contract(config)


def test_mainline_validator_rejects_unsigned_signedness_drift():
    config = load_contract(CONTRACT_PATH)
    config = deepcopy(config)
    config["numeric_contract"]["gelu_output"]["signedness"] = "signed"

    with pytest.raises(ValueError, match="mainline numeric contract"):
        validate_mainline_contract(config)
