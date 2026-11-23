# Cumulative sensitivity

| Rank | Experiment | Perturbation direction | Tensor metric direction | Top-1 | Top-5 | Drop (pp) | Samples |
|---:|---|---|---|---:|---:|---:|---:|
| — | cumulative-low-01 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.686260 | 0.890180 | 1.394000 | 50000 |
| — | cumulative-low-02 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.626600 | 0.845020 | 7.360000 | 50000 |
| — | cumulative-low-03 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.416280 | 0.667380 | 28.392000 | 50000 |
| — | cumulative-low-04 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.172100 | 0.310660 | 52.810000 | 50000 |
| — | cumulative-low-05 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.053260 | 0.117420 | 64.694000 | 50000 |
| — | cumulative-low-06 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.016000 | 0.041860 | 68.420000 | 50000 |
| — | cumulative-low-07 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.003200 | 0.014160 | 69.700000 | 50000 |
| — | cumulative-low-08 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.001620 | 0.008520 | 69.858000 | 50000 |
| — | cumulative-low-09 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.001340 | 0.006800 | 69.886000 | 50000 |
| — | cumulative-low-10 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.000740 | 0.004360 | 69.946000 | 50000 |
| — | cumulative-low-11 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.001080 | 0.004520 | 69.912000 | 50000 |
| — | cumulative-low-12 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.000960 | 0.005480 | 69.924000 | 50000 |
| — | cumulative-rear-01 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.686260 | 0.890180 | 1.394000 | 50000 |
| — | cumulative-rear-02 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.626600 | 0.845020 | 7.360000 | 50000 |
| — | cumulative-rear-03 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.416280 | 0.667380 | 28.392000 | 50000 |
| — | cumulative-rear-04 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.172100 | 0.310660 | 52.810000 | 50000 |
| — | cumulative-rear-05 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.053260 | 0.117420 | 64.694000 | 50000 |
| — | cumulative-rear-06 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.008280 | 0.023500 | 69.192000 | 50000 |
| — | cumulative-rear-07 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.001960 | 0.008640 | 69.824000 | 50000 |
| — | cumulative-rear-08 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.001520 | 0.006220 | 69.868000 | 50000 |
| — | cumulative-rear-09 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.001200 | 0.005840 | 69.900000 | 50000 |
| — | cumulative-rear-10 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.001140 | 0.005160 | 69.906000 | 50000 |
| — | cumulative-rear-11 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.001080 | 0.004520 | 69.912000 | 50000 |
| — | cumulative-rear-12 | FP32_activation_to_strict_quantized | FP32_activation_to_strict_quantized | 0.000960 | 0.005480 | 69.924000 | 50000 |

Perturbation direction describes the model change; tensor metric direction describes the before/after pair used for error statistics.

Top-1 drop is relative to the baseline in percentage points. All rows use the same 50,000-image crop09 role when this is a formal report.

## Frozen identity

- config_sha256: `87e13d16f7a95ac7989467af6087f626f4939a948dc6c4035829a408a606d9ab`
- checkpoint_sha256: `b449e4572c27bc382571b5e34a1939e79a14b5e0aff6d9f392fa9bf307c98aab`
- data_sha256: `4756b1af44e3b44a1346b9b7e58b20e4aa92b3e6da8649ac038852ed321cf15b`
- scales_sha256: `c2648ccacd57e79b636fc84805f7d52fa45efa0ed79cbd0b14214206a8cd2b31`
