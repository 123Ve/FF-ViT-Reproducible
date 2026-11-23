#!/usr/bin/env bash
set -euo pipefail

RE=/home/user/Desktop/ff_vit_re
HLS=/home/user/Desktop/FF_Vit/flash_vit_2
SRC="$HLS/src"
CFG="$HLS/flash_vit/hls_config_bitaccurate.cfg"
WORK="$HLS/flash_vit/vit_plantvillage_bitaccurate"
LOG="$HLS/flash_vit/csim_plantvillage_bitaccurate.log"

echo "===== PRECHECK ====="
command -v vitis-run >/dev/null || {
  echo "ERROR: vitis-run not found. Source the Vitis 2025.1 settings64.sh first."
  exit 2
}

# Remove accidental NUL bytes from C/C++ text sources, with one-time backups.
python - <<'PY'
from pathlib import Path
root = Path("/home/user/Desktop/FF_Vit/flash_vit_2/src")
exts = {".h", ".hpp", ".c", ".cc", ".cpp"}
for p in root.rglob("*"):
    if p.is_file() and p.suffix in exts:
        b = p.read_bytes()
        n = b.count(b"\x00")
        if n:
            bak = p.with_name(p.name + ".pre_nul_cleanup.bak")
            if not bak.exists():
                bak.write_bytes(b)
            p.write_bytes(b.replace(b"\x00", b""))
            print(f"removed {n} NUL bytes: {p}")
PY

echo
echo "Head typedefs:"
grep -an \
'__head_ln_sum_t\|__head_ln_divc_t\|__head_ln_mu_t\|__head_ln_cursor_t' \
"$SRC/block0.cpp"

echo
echo "Active weights:"
stat -c '%n %s bytes' "$HLS/weights.bin"
test "$(stat -c '%s' "$HLS/weights.bin")" = "2772096"

if [ -f "$RE/stage4p_hls_deploy_v2/weights.bin" ]; then
  cmp -s "$RE/stage4p_hls_deploy_v2/weights.bin" "$HLS/weights.bin" || {
    echo "ERROR: active weights.bin differs from Stage4P v2."
    exit 3
  }
  echo "ACTIVE WEIGHTS OK"
fi

echo
echo "===== GENERATE NEW BIT-ACCURATE FIXTURE ====="
cd "$RE"

python -u stage4q_generate_csim_fixture_v2.py \
  --output ./stage4q_csim_fixture \
  --split val \
  --image-index 0 \
  --install-dir "$HLS" \
  2>&1 | tee stage4q_csim_fixture.log

echo
echo "Fixture sizes:"
stat -c '%n %s bytes' "$HLS/input.bin" "$HLS/output.bin"
test "$(stat -c '%s' "$HLS/input.bin")" = "602112"
test "$(stat -c '%s' "$HLS/output.bin")" = "4000"

echo
echo "===== WRITE DEDICATED C-SIM CONFIG ====="
cat > "$CFG" <<EOF
part=xczu9eg-ffvb1156-2-i

[hls]
flow_target=vivado
clock=5ns
syn.top=vit_block_top
syn.file=$SRC/block0.cpp

tb.file=$HLS/weights.bin
tb.file=$HLS/input.bin
tb.file=$HLS/output.bin

csim.clean=true
csim.code_analyzer=0
EOF

cat "$CFG"

echo
echo "===== RUN TRUE 1000-LOGIT C-SIM ====="
rm -rf "$WORK"

vitis-run \
  --mode hls \
  --csim \
  --config "$CFG" \
  --work_dir "$WORK" \
  2>&1 | tee "$LOG"

echo
echo "===== RESULT SUMMARY ====="

# Search both the outer log and work directory logs.
grep -aE \
'C-Sim Final Logits Compare|Logit\[|FPGA class ID|PASS!|FAIL!|Mismatch|MISMATCH' \
"$LOG" | tail -80 || true

echo
echo "Full log: $LOG"
echo "Work dir: $WORK"

if grep -aq 'PASS!' "$LOG" && ! grep -aq 'FAIL!' "$LOG" && ! grep -aq 'MISMATCH' "$LOG"; then
  echo
  echo "=============================================="
  echo "  1000-LOGIT C-SIM PASS"
  echo "=============================================="
  exit 0
fi

# Do NOT grep binaries for the literal "PASS!" string: block0.o/csim.exe
# contain both PASS and FAIL format strings and caused a false positive before.
CSIM_REPORT="$WORK/hls/csim/report/vit_block_top_csim.log"

if [ -f "$CSIM_REPORT" ]; then
  if grep -aq 'FAIL!' "$CSIM_REPORT" || grep -aq 'MISMATCH' "$CSIM_REPORT"; then
    echo
    echo "=============================================="
    echo "  1000-LOGIT C-SIM FAIL"
    echo "=============================================="
    grep -aE 'Logit\[|FPGA class ID|PASS!|FAIL!|MISMATCH' "$CSIM_REPORT" | tail -80 || true
    exit 1
  fi

  if grep -aq 'PASS!' "$CSIM_REPORT"; then
    echo
    echo "=============================================="
    echo "  1000-LOGIT C-SIM PASS"
    echo "=============================================="
    exit 0
  fi
fi

echo
echo "C-sim did not report a trustworthy PASS. Inspect: $CSIM_REPORT"
exit 1
