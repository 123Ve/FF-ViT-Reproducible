#!/usr/bin/env bash
# Wait for this single implementation, then build PS/BOOT only on gate success.
set -euo pipefail
E07_TASK_ROOT=$(cd "$(dirname "$0")/.." && pwd)
E07_TASK_LOG="$E07_TASK_ROOT/results/candidate04"
export PATH=/opt/vivado/2025.1/Vitis/bin:/opt/vivado/2025.1/Vivado/bin:$PATH
if [[ -e "$E07_TASK_LOG/board_build_status.log" ]]; then
    echo "Board continuation already started" >&2
    exit 2
fi
stage=await_implementation
finish() {
    rc=$?
    printf '%s exit=%s stage=%s\n' "$(date --iso-8601=seconds)" "$rc" "$stage" >> "$E07_TASK_LOG/board_build_status.log"
    printf '%s\n' "$rc" > "$E07_TASK_LOG/board_build.exit"
}
trap finish EXIT
printf '%s START %s\n' "$(date --iso-8601=seconds)" "$stage" >> "$E07_TASK_LOG/board_build_status.log"
while [[ ! -f "$E07_TASK_LOG/implementation.exit" ]]; do sleep 60; done
if [[ $(< "$E07_TASK_LOG/implementation.exit") != 0 ]]; then
    stage=hardware_rejected_no_board_image
    exit 1
fi
run_stage() {
    stage=$1
    shift
    printf '%s START %s\n' "$(date --iso-8601=seconds)" "$stage" >> "$E07_TASK_LOG/board_build_status.log"
    "$@" > "$E07_TASK_LOG/$stage.log" 2>&1
    printf '%s PASS %s\n' "$(date --iso-8601=seconds)" "$stage" >> "$E07_TASK_LOG/board_build_status.log"
}
cd "$E07_TASK_ROOT"
run_stage final_release_gate python3 scripts/check_release.py "$E07_TASK_LOG"
export E07_XSA="$E07_TASK_LOG/e07_300mhz_wrapper.xsa"
export E07_CLOCK_FILE="$E07_TASK_LOG/clock.txt"
run_stage vitis_build vitis -s board_300mhz/build_vitis.py
run_stage pmufw vitis -s board_300mhz/build_pmufw.py
run_stage bootgen python3 board_300mhz/make_boot_image.py
cd "$E07_TASK_ROOT/../.."
stage=final_e06_identity
sha256sum --check --quiet "$E07_TASK_ROOT/results/frozen_e06_full.sha256"
stage=boot_image_built_board_validation_pending
