#!/usr/bin/env bash
# One implementation after successful preparation; retain earlier diagnostics.
set -euo pipefail
E07_TASK_ROOT=$(cd "$(dirname "$0")/.." && pwd)
E07_TASK_LOG="$E07_TASK_ROOT/results/candidate04"
export PATH=/opt/vivado/2025.1/Vitis/bin:/opt/vivado/2025.1/Vivado/bin:$PATH
if [[ ! -f "$E07_TASK_LOG/clock.txt" || -e "$E07_TASK_LOG/implement_vivado.log" ]]; then
    echo "Preparation missing or implementation already attempted" >&2
    exit 2
fi
stage=resume_identity
finish() {
    rc=$?
    printf '%s exit=%s stage=%s\n' "$(date --iso-8601=seconds)" "$rc" "$stage" >> "$E07_TASK_LOG/build_status.log"
    printf '%s\n' "$rc" > "$E07_TASK_LOG/implementation.exit"
}
trap finish EXIT
cd "$E07_TASK_ROOT/../.."
sha256sum --check --quiet "$E07_TASK_ROOT/results/frozen_e06_full.sha256"
cd "$E07_TASK_ROOT"
sha256sum --check --quiet results/candidate02/reused_ip_identity.sha256
python3 tests/test_release_gate.py > "$E07_TASK_LOG/release_tests_current.log" 2>&1
stage=implement
printf '%s START %s after_prepare_retry2_pass\n' "$(date --iso-8601=seconds)" "$stage" >> "$E07_TASK_LOG/build_status.log"
vivado -mode batch -notrace -source scripts/run_candidate04.tcl -log "$E07_TASK_LOG/implement_vivado.log" -journal "$E07_TASK_LOG/implement_vivado.jou" > "$E07_TASK_LOG/implement.log" 2>&1
stage=hardware_pass_board_build_pending
