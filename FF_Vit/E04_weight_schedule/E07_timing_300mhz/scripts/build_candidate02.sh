#!/usr/bin/env bash
# Unchanged HLS IP/C regression; independent PS clock and fresh retimed P&R.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
export PATH=/opt/vivado/2025.1/Vitis/bin:/opt/vivado/2025.1/Vivado/bin:$PATH
LOG="$ROOT/results/candidate02"
if [[ -e "$LOG/build_status.log" || -e "$ROOT/vivado_candidate02/e07.xpr" ]]; then
    echo "Refusing to overwrite candidate02" >&2
    exit 2
fi
mkdir -p "$LOG"
stage=identity
finish() {
    rc=$?
    printf '%s exit=%s stage=%s\n' "$(date --iso-8601=seconds)" "$rc" "$stage" >> "$LOG/build_status.log"
    printf '%s\n' "$rc" > "$LOG/build.exit"
}
trap finish EXIT
run_stage() {
    stage=$1
    shift
    printf '%s START %s\n' "$(date --iso-8601=seconds)" "$stage" >> "$LOG/build_status.log"
    "$@" > "$LOG/$stage.log" 2>&1
    printf '%s PASS %s\n' "$(date --iso-8601=seconds)" "$stage" >> "$LOG/build_status.log"
}
cd "$ROOT/../.."
sha256sum --check --quiet "$ROOT/results/frozen_e06_full.sha256"
cd "$ROOT"
cp results/candidate01/csim.log "$LOG/csim.log"
sha256sum src/block0.cpp hls/work/hls/impl/ip/component.xml ip/vit_block_top.zip results/candidate01/csim.log > "$LOG/reused_ip_identity.sha256"
run_stage release_tests python3 tests/test_release_gate.py
run_stage prepare vivado -mode batch -notrace -source scripts/prepare_candidate02.tcl -log "$LOG/prepare_vivado.log" -journal "$LOG/prepare_vivado.jou"
run_stage implement vivado -mode batch -notrace -source scripts/run_candidate02.tcl -log "$LOG/implement_vivado.log" -journal "$LOG/implement_vivado.jou"
run_stage release_gate python3 scripts/check_release.py "$LOG"
export E07_XSA="$LOG/e07_300mhz_wrapper.xsa"
export E07_CLOCK_FILE="$LOG/clock.txt"
run_stage vitis_build vitis -s board_300mhz/build_vitis.py
run_stage pmufw vitis -s board_300mhz/build_pmufw.py
run_stage bootgen python3 board_300mhz/make_boot_image.py
cd "$ROOT/../.."
stage=final_identity
sha256sum --check --quiet "$ROOT/results/frozen_e06_full.sha256"
stage=complete_board_validation_pending
