#!/usr/bin/env bash
# Candidate01: fail at the first failed stage. All outputs stay in E07.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
export PATH=/opt/vivado/2025.1/Vitis/bin:/opt/vivado/2025.1/Vivado/bin:$PATH
LOG="$ROOT/results/candidate01"
mkdir -p "$LOG"
cd "$ROOT"
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
cd ../..
sha256sum --check --quiet "$ROOT/results/frozen_e06_full.sha256"
cd "$ROOT"
run_stage release_tests python3 tests/test_release_gate.py
if [[ $# -eq 0 ]]; then
    run_stage hls_synth v++ -c --mode hls --config hls/hls_config.cfg --work_dir hls/work
    run_stage package vitis-run --mode hls --package --config hls/hls_config.cfg --work_dir hls/work
    run_stage prepare vivado -mode batch -notrace -source scripts/prepare_vivado.tcl -log "$LOG/prepare_vivado.log" -journal "$LOG/prepare_vivado.jou"
elif [[ $# -eq 1 && $1 == --resume-after-package ]]; then
    # Only resume the generated, never-synthesized E07 project. Preserve the
    # original failed preparation log and the completed HLS/package evidence.
    export E07_RESUME_PREPARE=1
    run_stage prepare_resume vivado -mode batch -notrace -source scripts/prepare_vivado.tcl -log "$LOG/prepare_resume_vivado.log" -journal "$LOG/prepare_resume_vivado.jou"
else
    echo "usage: build.sh [--resume-after-package]" >&2
    exit 2
fi
run_stage implement vivado -mode batch -notrace -source scripts/run_vivado.tcl -log "$LOG/implement_vivado.log" -journal "$LOG/implement_vivado.jou"
run_stage release_gate python3 scripts/check_release.py "$LOG"
export E07_XSA="$LOG/e07_300mhz_wrapper.xsa"
run_stage vitis_build vitis -s board_300mhz/build_vitis.py
run_stage pmufw vitis -s board_300mhz/build_pmufw.py
run_stage bootgen python3 board_300mhz/make_boot_image.py
cd ../..
stage=final_identity
sha256sum --check --quiet "$ROOT/results/frozen_e06_full.sha256"
stage=complete_board_validation_pending
