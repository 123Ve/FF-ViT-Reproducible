# Approved progressive E07 U3 QAT

Only PlantVillage and NWPU. No ImageNet, original checkpoint, HLS/RTL or bitstream writes.

1. Tests first: 6/9/12 active block quantizers; inactive blocks unchanged;
   U3 Softmax receives gradients and cannot be bypassed by timm fused attention.
2. Reuse original W3 checkpoint and MLP/Attention controllers. Train MLP then
   Attention, 10 epochs each, batch32, AdamW model1e-5/scale5e-4,
   WD0.02/0, cosine, clip1, KD alpha0.5/T2. Validation always all12.
   Add U3 Softmax, Q12/K11/V11 raw-MAC and A11 boundaries, and couple
   Attention residual scale to actual A_scale*W_O_scale. These are deliberate
   differences from original float-Softmax QAT, not exact-forward training.
3. Freeze calibration256 and validation/test membership; calibration and held-out
   content excluded from optimizer samples. Log hashes, stages, active quantizers,
   best/last and RNG/optimizer state. Keep best by validation only. FP32 training,
   no AMP (explicit difference from original AMP script).
4. Independently refit all 12 integer/LUT blocks from the selected trained state,
   learned scales and real propagated calibration codes. Preserve frozen Patch.
   Fit original unsigned E07 Head (U15/U30/U7/U24/U6/U11/S36/S9/S8).
5. Full validation/test exact integer/LUT software; 128 historic image local
   Softmax/LN/GELU errors and GELU2048-code exhaust. Fake-quant accuracy must
   remain separate. New HLS C-sim/RTL/FPGA = NOT_MEASURED.
6. Verify export/reload and source hashes. Save CSV/JSON and status; never claim
   final accuracy before actual evaluation. Any interruption keeps resumable state.
