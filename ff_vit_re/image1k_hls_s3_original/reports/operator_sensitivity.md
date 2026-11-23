# Operator sensitivity

| Rank | Experiment | Perturbation direction | Tensor metric direction | Top-1 | Top-5 | Drop (pp) | Samples |
|---:|---|---|---|---:|---:|---:|---:|
| — | baseline | no_perturbation | not_applicable | 0.700200 | 0.898700 | 0.000000 | 50000 |
| 8 | operator-ln1 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.638820 | 0.862740 | 6.138000 | 50000 |
| 13 | operator-q | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.685960 | 0.891080 | 1.424000 | 50000 |
| 16 | operator-k | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.695200 | 0.896560 | 0.500000 | 50000 |
| 15 | operator-v | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.690100 | 0.891720 | 1.010000 | 50000 |
| 11 | operator-a | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.675980 | 0.883620 | 2.422000 | 50000 |
| 4 | operator-softmax | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.123220 | 0.242680 | 57.698000 | 50000 |
| 5 | operator-ln2 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.466680 | 0.724880 | 23.352000 | 50000 |
| 3 | operator-gelu | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.065580 | 0.171980 | 63.462000 | 50000 |
| 10 | operator-fc1_weight | W3_to_FP32_removal_ablation | FP32_master_to_W3_quantized | 0.663960 | 0.876480 | 3.624000 | 50000 |
| 14 | operator-fc2_weight | W3_to_FP32_removal_ablation | FP32_master_to_W3_quantized | 0.686980 | 0.892100 | 1.322000 | 50000 |
| 12 | operator-attention_residual | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.682840 | 0.891040 | 1.736000 | 50000 |
| 7 | operator-mlp_residual | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.605560 | 0.837920 | 9.464000 | 50000 |
| 9 | group-qkv | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.658560 | 0.873280 | 4.164000 | 50000 |
| 6 | group-attention-all | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.553520 | 0.802020 | 14.668000 | 50000 |
| 2 | group-mlp-all | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.032960 | 0.101780 | 66.724000 | 50000 |
| 1 | group-all-a3 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.006420 | 0.026680 | 69.378000 | 50000 |

Perturbation direction describes the model change; tensor metric direction describes the before/after pair used for error statistics.

Top-1 drop is relative to the baseline in percentage points. All rows use the same 50,000-image crop09 role when this is a formal report.

## Frozen identity

- config_sha256: `87e13d16f7a95ac7989467af6087f626f4939a948dc6c4035829a408a606d9ab`
- checkpoint_sha256: `b449e4572c27bc382571b5e34a1939e79a14b5e0aff6d9f392fa9bf307c98aab`
- data_sha256: `4756b1af44e3b44a1346b9b7e58b20e4aa92b3e6da8649ac038852ed321cf15b`
- scales_sha256: `c2648ccacd57e79b636fc84805f7d52fa45efa0ed79cbd0b14214206a8cd2b31`
