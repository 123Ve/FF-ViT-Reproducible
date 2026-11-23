"""Load and validate the experiment's frozen numeric contract."""

from pathlib import Path
from typing import Any

import yaml


EXPECTED_NUMERIC_CONTRACT = {
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


def load_contract(path: str | Path) -> dict[str, Any]:
    """Read a YAML contract and ensure its top-level value is a mapping."""
    contract_path = Path(path)
    with contract_path.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise ValueError(f"contract must contain a YAML mapping: {contract_path}")
    return config


def validate_mainline_contract(config: dict[str, Any]) -> None:
    """Raise ValueError unless all mainline boundaries retain exact HLS widths."""
    actual = config.get("numeric_contract")
    if not isinstance(actual, dict):
        raise ValueError("mainline numeric contract must be a mapping")

    differences = []
    for boundary, (signedness, bits) in EXPECTED_NUMERIC_CONTRACT.items():
        value = actual.get(boundary)
        if not isinstance(value, dict):
            differences.append(f"{boundary}=missing")
            continue
        observed = (value.get("signedness"), value.get("bits"))
        expected = (signedness, bits)
        if observed != expected:
            differences.append(
                f"{boundary} expected {signedness}{bits}, got "
                f"{observed[0]}{observed[1]}"
            )

    unexpected = sorted(set(actual) - set(EXPECTED_NUMERIC_CONTRACT))
    differences.extend(f"{boundary}=unexpected" for boundary in unexpected)
    if differences:
        detail = "; ".join(differences)
        raise ValueError(f"mainline numeric contract mismatch: {detail}")
