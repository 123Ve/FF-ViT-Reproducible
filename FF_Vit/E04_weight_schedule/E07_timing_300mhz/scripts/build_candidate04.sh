#!/usr/bin/env bash
# Same checked HLS IP; one fresh clock-network implementation candidate.
set -euo pipefail
E07_TASK_ROOT=$(cd "$(dirname "$0")/.." && pwd)
export PATH=/opt/vivado/2025.1/Vitis/bin:/opt/vivado/2025.1/Vivado/bin:$PATH
E07_TASK_LOG="$E07_TASK_ROOT/results/candidate04"
if [[ -e "$E07_TASK_LOG/build_status.log" || -e "$E07_TASK_ROOT/vivado_candidate04/e07.xpr" ]]; then
    echo "Refusing to overwrite candidate04" >&2
    exit 2
fi
mkdir -p "$E07_TASK_LOG"
stage=identity
finish() {
    rc=$?
    printf '%s exit=%s stage=%s\n' "$(date --iso-8601=seconds)" "$rc" "$stage" >> "$E07_TASK_LOG/build_status.log"
    printf '%s\n' "$rc" > "$E07_TASK_LOG/build.exit"
}
trap finish EXIT
run_stage() {
    stage=$1
    shift
    printf '%s START %s\n' "$(date --iso-8601=seconds)" "$stage" >> "$E07_TASK_LOG/build_status.log"
    "$@" > "$E07_TASK_LOG/$stage.log" 2>&1
    printf '%s PASS %s\n' "$(date --iso-8601=seconds)" "$stage" >> "$E07_TASK_LOG/build_status.log"
}
cd "$E07_TASK_ROOT/../.."
sha256sum --check --quiet "$E07_TASK_ROOT/results/frozen_e06_full.sha256"
cd "$E07_TASK_ROOT"
sha256sum --check --quiet results/candidate02/reused_ip_identity.sha256
cp results/candidate01/csim.log "$E07_TASK_LOG/csim.log"
cp results/candidate02/reused_ip_identity.sha256 "$E07_TASK_LOG/reused_ip_identity.sha256"
run_stage release_tests python3 tests/test_release_gate.py
run_stage prepare vivado -mode batch -notrace -source scripts/prepare_candidate04.tcl -log "$E07_TASK_LOG/prepare_vivado.log" -journal "$E07_TASK_LOG/prepare_vivado.jou"
run_stage implement vivado -mode batch -notrace -source scripts/run_candidate04.tcl -log "$E07_TASK_LOG/implement_vivado.log" -journal "$E07_TASK_LOG/implement_vivado.jou"
run_stage release_gate python3 scripts/check_release.py "$E07_TASK_LOG"
# Platform and boot assembly are a separate gated stage, not an automatic retry.
stage=hardware_pass_board_build_pending
