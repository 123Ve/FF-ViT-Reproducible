# Original-width exact integer deployment

The selected source is `checkpoints/attention/main/best.pth`, SHA-256
`bf40fc4e40a27943f7b4e27b4b6e9dc9b45320c03b13ba181fb91fd81371fad3`.
Its `ema_model` and `ema_controller` are used together. The measured surrogate
Top-1 is 66.954%, not an exact-integer or FPGA measurement.

`exact/main/manifest.json` binds the selected checkpoint, original HLS source
files, local integer implementation, and calibration manifest by SHA-256.
The builder rejects changed source identities when resuming a cached block.
No original HLS source file is edited.

## Executed arithmetic versus unused typedefs

The authoritative source is `/home/user/Desktop/FF_Vit/flash_vit_2/src`.
`attn.h` instantiates `fused_flash_attn.h`, not the standalone `Softmax` class.
The fused kernel stores scores in `int S_buf`, computes the dot product with
`long long`, and keeps the quantized probability in `int rq_val`. Consequently,
the declared s10 score and u3 probability typedefs are not casts in this path.
The generated `softmax_scalars[13] = 3` enforces the requested 0..7 probability
range without changing source or widening any interface. The exact model
replays the executed fused arithmetic, including s11 subtraction, u8 first
cursor, u23 sum/product, u9/s7 reciprocal cursors, and s11 A output.

The standalone Softmax replay is retained only for primitive tests. Its u8
final cursor and u3 assignment must not be inserted into the fused path.

LN1/LN2 output s3, GELU u3, Q/K/V/A s3, all six encoder weights s3,
M1 s11, M2 s13, attention residual s15 and block residual s13 remain fixed.
Head follows the selected fixed-ROM path: sum s15, reciprocal product s30,
mean s7, variance u24, cursor u7, affine s36, shifted value s9, output s8,
W8 and bias/MAC s19. Patch output remains s13.

## Scale mapping and approximation

The surrogate learned independent activation scales at FC1, FC2, projection,
and residual boundaries. The original HLS does not have a post-MAC requantizer
at these positions. Deployment therefore uses each physical MAC scale
`input_activation_scale × weight_scale`; residual RM/RS maps the skip branch
into the MAC domain. The builder records both surrogate and physical M1/M2
scales. Their discrepancy is a real deployment approximation and cannot be
removed by describing surrogate accuracy as exact accuracy.

LN rsqrt/affine and GELU/QKV/A LUT parameters use the existing PlantVillage
histogram/search approach with ImageNet calibration tensors. Softmax exp uses
the PlantVillage 4096 code scale, retaining 32 exp entries and two 64-entry
reciprocal tables, with histogram address bias/shift search. Every emitted
Softmax output is clamped to u3.

The main build propagates all 2,000 frozen train calibration images through
the integer encoder. For bounded LUT fitting, each block selects 32 complete
images spread deterministically across those 2,000 members (6,272 tokens);
their exact indices are recorded per block. Head fitting uses all 2,000 CLS
vectors. This does not use the selection or validation split for LUT fitting.

## Reproduction

Use `/home/user/anaconda3/envs/vlm_token/bin/python` from this directory:

```bash
python scripts/build_exact.py --inventory-only
python scripts/build_exact.py --output exact/main --device cpu --samples 2000 --fit-tokens 6272
python scripts/evaluate_exact.py --artifact exact/main --output reports/exact_50k.json --device cuda
python scripts/compare_exact_surrogate.py --artifact exact/main --fixtures reports/exact_50k_shards/fixtures
```

The builder writes deterministic integer arrays, `weights.bin`,
`weights_fields.bin`, and `fixed_patch_head_rom.h`. Evaluation writes resumable
prediction shards, unique sample identities, integer fixture traces, and a
separate report. Probe runs require a different report filename. Equal integer
logits use ascending class ID as the tie-break. Full exact accuracy is valid
only after all 50,000 unique validation samples complete; HLS equivalence is
a separate subsequent gate.
