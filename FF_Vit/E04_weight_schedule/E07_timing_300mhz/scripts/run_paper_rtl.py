#!/usr/bin/env python3
"""One fresh E07 native RTL frame; no source/RTL writes or synthesis."""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import difflib
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def instance_paths(rtl):
    children = {}
    for path in rtl.glob("*.v"):
        text = path.read_text()
        name = re.search(r"^\s*module\s+(\w+)", text, re.M)
        if name:
            children[name[1]] = re.findall(r"^\s*(vit_block_top\w*)\s+(\w+)\s*\(", text, re.M)
    result = {}

    def walk(typ, path, ancestors):
        if typ in ancestors:
            raise ValueError(f"recursive hierarchy: {typ}")
        result.setdefault(typ, []).append(path)
        for child, inst in children.get(typ, []):
            walk(child, path + "." + inst, ancestors | {typ})

    walk("vit_block_top", "AESL_inst_vit_block_top", set())
    return result


def unique_path(paths, typ):
    found = paths.get(typ, [])
    if len(found) != 1:
        raise ValueError(f"ambiguous/missing {typ}: {found}")
    return found[0]


def setup_config(root):
    rows = []
    for line in (root / "hls/hls_config.cfg").read_text().splitlines():
        if line.startswith(("syn.file=", "tb.file=")):
            key, value = line.split("=", 1)
            line = f"{key}={(root / 'hls' / value).resolve()}"
        if line.startswith("cosim.enable_dataflow_profiling="):
            line = "cosim.enable_dataflow_profiling=0"
        if line.startswith("cosim.trace_level="):
            line = "cosim.trace_level=none"
        if line.startswith("package.output.file="):
            continue
        rows.append(line)
    return "\n".join(rows) + "\ncosim.setup=1\n"


def discover_mac(rtl):
    observer = load(WORKSPACE / "E04_weight_schedule/diagnostic/rtl_mac_activity_observer.py", "e07_mac_discovery")
    paths = instance_paths(rtl)
    specs = [
        ("Patch", "fixed_patch_step2_mac_replace_shift_Pipeline_CIT_LOOP_COT_LOOP", 576, "icmp_ln238_fu_6732_p2", "patch", -1),
        ("Q", "matmul_step2_mac_2", 512, None, "projection", -1),
        ("K", "matmul_step2_mac_11", 512, None, "projection", -1),
        ("V", "matmul_step2_mac_4", 512, None, "projection", -1),
        *[(f"QK{i}", f"do_attn{s}_Pipeline_PASS1_J_LOOP", 256, "icmp_ln207_fu_1860_p2", "qk", i) for i, s in enumerate(("_6", "_7", ""))],
        *[(f"AV{i}", f"do_attn{s}_Pipeline_PASS3_J_LOOP", 256, "icmp_ln285_fu_3114_p2", "av", i) for i, s in enumerate(("_6", "_7", ""))],
        ("O", "matmul_step2_mac_1", 576, None, "projection", -1),
        ("MLP1", "matmul_step2_mac_3", 1024, None, "matrix", -1),
        ("MLP2", "matmul_step2_mac", 1024, None, "matrix", -1),
        ("Head", "fixed_head_matmul_core_Pipeline_COT_LOOP_CIT_LOOP", 8, "icmp_ln411_fu_443_p2", "head", -1),
    ]
    rows = []
    for module, suffix, lanes, predicate, stage, head in specs:
        typ = "vit_block_top_" + suffix
        path = rtl / (typ + ".v")
        hierarchy = unique_path(paths, typ)
        if predicate:
            row = observer._pipeline_leaf(path, module, hierarchy, lanes, predicate, stage, head,
                                           "mac_sm_full_n" if module in ("Patch", "Head") else None)
        else:
            row = observer.discover_matrix_leaf(path, module, hierarchy, lanes)
        rows.append(row)
    return {"version": "E07", "schema_version": "E07_PAPER_AGGREGATE_V1", "modules": rows,
            "layer_expression": "AESL_inst_vit_block_top.l_fu_5688",
            "frame_start_expression": "AESL_inst_vit_block_top.ap_start",
            "frame_done_expression": "AESL_inst_vit_block_top.ap_done",
            "rtl_sha256": {p.name: sha(p) for p in sorted(rtl.glob("*")) if p.is_file()},
            "instance_paths": paths}


def render_monitor(schema):
    rows = schema["modules"]
    lines = ["// E07_PAPER_AGGREGATE_V1: accepted ISSUE only, never completion double count.",
             "integer ep_fd, ep_pf, ep_qfd, ep_af, ep_i, ep_j, ep_l, ep_total, ep_issue, ep_mask;",
             "integer ep_peak, ep_peak_mask, ep_peak_cycle, ep_exclusive_errors;",
             "integer ep_first[0:195], ep_last[0:195], ep_count[0:195];",
             "integer ep_residence[0:195], ep_input[0:195], ep_output[0:195];",
             "reg ep_active[0:13]; reg [13:0] ep_issue_bits;",
             "reg [63:0] ep_valid[0:195], ep_issued[0:195];",
             "reg [63:0] ep_ar, ep_bytes, ep_beats;",
             "initial begin",
             'ep_fd=$fopen("E07_RTL_Modules.csv","w");',
             'ep_qfd=$fopen("E07_RTL_Module_Layers.csv","w");',
             'ep_af=$fopen("E07_RTL_Aggregate.csv","w");',
             '$fwrite(ep_fd,"module,layer,logical_lanes,issue_count,first_issue,last_issue,observed_cycles,valid_MAC,issued_MAC,input_empty_noissue_cycles,output_full_noissue_cycles\\n");',
             '$fwrite(ep_qfd,"module,layer,logical_lanes,issue_count,first_issue,last_issue,observed_cycles,valid_MAC,issued_MAC,input_empty_noissue_cycles,output_full_noissue_cycles\\n");',
             '$fwrite(ep_af,"peak_valid_MAC,peak_module_mask,peak_cycle,exclusive_errors,axi_ar_requests,axi_requested_bytes,axi_r_beats\\n");',
             "ep_peak=0; ep_peak_mask=0; ep_peak_cycle=-1; ep_exclusive_errors=0; ep_ar=0; ep_bytes=0; ep_beats=0;",
             "for(ep_i=0;ep_i<14;ep_i=ep_i+1) ep_active[ep_i]=0;",
             "for(ep_i=0;ep_i<196;ep_i=ep_i+1) begin ep_first[ep_i]=-1; ep_last[ep_i]=-1; ep_count[ep_i]=0; ep_residence[ep_i]=0; ep_input[ep_i]=0; ep_output[ep_i]=0; ep_valid[ep_i]=0; ep_issued[ep_i]=0; end",
             "end",
             "always @(posedge AESL_clock) begin",
             "ep_total=0; ep_issue=0; ep_mask=0; ep_issue_bits=0;",
             "if(AESL_inst_vit_block_top.m_axi_gmem_w_ARVALID && AESL_inst_vit_block_top.m_axi_gmem_w_ARREADY) begin ep_ar=ep_ar+1; ep_bytes=ep_bytes+((AESL_inst_vit_block_top.m_axi_gmem_w_ARLEN+1)<<AESL_inst_vit_block_top.m_axi_gmem_w_ARSIZE); end",
             "if(AESL_inst_vit_block_top.m_axi_gmem_w_RVALID && AESL_inst_vit_block_top.m_axi_gmem_w_RREADY) ep_beats=ep_beats+1;"]
    for index, row in enumerate(rows):
        layer = "0" if row["module"] == "Patch" else ("13" if row["module"] == "Head" else schema["layer_expression"] + "+1")
        effective = f"(({row['hierarchy']}.tt==0)?288:576)" if row["module"] == "Patch" else str(row["logical_lanes"])
        lines += [f"ep_l={index}*14+({layer});",
                  f"if({row['window_start_expression']} && !{row['window_done_expression']}) ep_active[{index}]=1;",
                  f"if(ep_active[{index}]) ep_residence[ep_l]=ep_residence[ep_l]+1;",
                  f"if({row['issue_expression']}) begin",
                  f"ep_issue_bits[{index}]=1; ep_count[ep_l]=ep_count[ep_l]+1; if(ep_first[ep_l]<0) ep_first[ep_l]=clk_cnt; ep_last[ep_l]=clk_cnt;",
                  f"ep_valid[ep_l]=ep_valid[ep_l]+{effective}; ep_issued[ep_l]=ep_issued[ep_l]+{row['logical_lanes']};",
                  f"ep_total=ep_total+{effective}; ep_mask=ep_mask+{1<<index};",
                  f"end else if(ep_active[{index}]) begin",
                  f"if({row['input_empty_expression']}) ep_input[ep_l]=ep_input[ep_l]+1;",
                  f"if({row['output_full_expression']}) ep_output[ep_l]=ep_output[ep_l]+1; end",
                  f"if({row['window_done_expression']}) ep_active[{index}]=0;"]
    lines += ["if((ep_issue_bits[4] && ep_issue_bits[7]) || (ep_issue_bits[5] && ep_issue_bits[8]) || (ep_issue_bits[6] && ep_issue_bits[9])) ep_exclusive_errors=ep_exclusive_errors+1;",
              "if(ep_total>ep_peak) begin ep_peak=ep_total; ep_peak_mask=ep_mask; ep_peak_cycle=clk_cnt; end",
              f"if({schema['frame_done_expression']}) begin",
              '$fwrite(ep_af,"%0d,%0d,%0d,%0d,%0d,%0d,%0d\\n",ep_peak,ep_peak_mask,ep_peak_cycle,ep_exclusive_errors,ep_ar,ep_bytes,ep_beats);']
    for index, row in enumerate(rows):
        lines += [f"for(ep_j=0;ep_j<14;ep_j=ep_j+1) begin ep_l={index}*14+ep_j; if(ep_count[ep_l]>0) begin",
                  f'$fwrite(ep_qfd,"{row["module"]},%0d,{row["logical_lanes"]},%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d\\n",ep_j-1,ep_count[ep_l],ep_first[ep_l],ep_last[ep_l],ep_residence[ep_l],ep_valid[ep_l],ep_issued[ep_l],ep_input[ep_l],ep_output[ep_l]);',
                  f"end end"]
    lines += ["$fflush(ep_fd); $fflush(ep_qfd); $fflush(ep_af); end end",
              'initial begin forever begin repeat(100000) @(posedge AESL_clock); $display("E07_PAPER_HEARTBEAT cycle=%0d layer=%0d",clk_cnt,AESL_inst_vit_block_top.l_fu_5688); end end']
    return "\n".join(lines) + "\n"


def stage_monitor(tb, rtl):
    observer = load(WORKSPACE / "E04_weight_schedule/diagnostic/timeline_observer.py", "e07_stage_discovery")
    _, schema = observer.generate_timeline_observer(tb, rtl, topology="prefetch")
    lines = ["integer eps_fd;", "initial begin", 'eps_fd=$fopen("e04_raw_events.csv","w");',
             '$fwrite(eps_fd,"cycle,event,event_specific_fields\\n");', "end"]
    blocks = []
    for index, (role, meta) in enumerate(schema["roles"].items()):
        fields = [key for key in ("ap_start", "ap_done", "curr_layer", "p_read", "num_layers")
                  if meta["signals"].get(key, {}).get("status") == "PRESENT"]
        meta["event_columns"] = fields
        expressions = [meta["signals"][key]["path"] for key in fields]
        packed = "{" + ",".join(expressions) + "}"
        lines += [f"reg [255:0] eps_prev_{index}; reg eps_seen_{index};",
                  f"initial begin eps_prev_{index}=0; eps_seen_{index}=0; end"]
        fmt = ",".join(["%0d", meta["event"]] + ["%h"] * len(fields)) + "\\n"
        blocks += [f"if(!eps_seen_{index} || ({packed} !== eps_prev_{index})) begin",
                   f'$fwrite(eps_fd,"{fmt}",clk_cnt,{",".join(expressions)});',
                   f"eps_prev_{index}={packed}; eps_seen_{index}=1; end"]
    lines += ["always @(posedge AESL_clock) begin", *blocks, "end"]
    return "\n".join(lines) + "\n", schema


def analyze(result, sim, schema, stage_schema, full, helper):
    performance = full.resolve_transaction_report(sim)
    shutil.copy2(performance, result / performance.name)
    match = re.search(r"transaction\s+0:\s+(\d+)\s+(\d+|x)", performance.read_text())
    if not match:
        raise ValueError("missing complete native frame report")
    latency = int(match[1])
    check = full.compare_first_output_transaction(sim)
    (result / "output_check.json").write_text(json.dumps(check, indent=2))
    if check["status"] != "PASS":
        raise ValueError("logits/AXIS postcheck failed")
    def read(name):
        path = sim / "verilog" / name
        shutil.copy2(path, result / name)
        with path.open() as handle:
            return list(csv.DictReader(handle))
    layers = read("E07_RTL_Module_Layers.csv")
    counts = {}
    effective = issued = 0
    for row in layers:
        counts[row["module"]] = counts.get(row["module"], 0) + int(row["issue_count"])
        effective += int(row["valid_MAC"])
        issued += int(row["issued_MAC"])
    analyzer = load(WORKSPACE / "E04_weight_schedule/diagnostic/analyze_rtl_mac_activity.py", "e07_reconcile")
    recon = analyzer.reconcile_counts(counts)
    if recon["status"] != "PASS" or effective != 1_246_416_384 or issued != 1_246_563_840:
        raise ValueError(f"MAC reconciliation failure: {recon}, effective={effective}, issued={issued}")
    aggregate = read("E07_RTL_Aggregate.csv")
    if len(aggregate) != 1 or int(aggregate[0]["exclusive_errors"]):
        raise ValueError("ambiguous frame count or QK/AV exclusivity violation")
    for module in ("Q", "K", "V", "O", "MLP1", "MLP2"):
        selected = [row for row in layers if row["module"] == module]
        if {int(row["layer"]) for row in selected} != set(range(12)):
            raise ValueError(f"missing layer attribution for {module}")
    timeline = load(WORKSPACE / "E04_weight_schedule/E06_mlp_ln_token_pipeline/scripts/run_rtl_frame_timeline.py", "e07_timeline_analysis")
    raw = sim / "verilog/e04_raw_events.csv"
    shutil.copy2(raw, result / raw.name)
    events = timeline.read_raw_events(raw)
    timeline.CANONICAL_FRAME_CYCLES = latency
    stage_analysis = timeline.analyze_timeline(events, stage_schema, result)
    # Rename E06 helper output names; numeric values are from the new E07 events.
    for p in result.glob("E06_*.csv"):
        p.rename(p.with_name(p.name.replace("E06_", "E07_", 1)))
    qrows = sorted([row for row in layers if row["module"] == "Q"], key=lambda row: int(row["layer"]))
    peak_mask = int(aggregate[0]["peak_module_mask"])
    output = {"version": "E07", "status": "PASS", "evidence_class": "RTL_OBSERVATION",
              "frame_latency_cycles": latency, "frame_start_interval_cycles": None,
              "effective_MAC": effective, "issued_MAC": issued,
              "observed_peak_MAC_per_cycle": int(aggregate[0]["peak_valid_MAC"]),
              "observed_peak_modules": [row["module"] for i, row in enumerate(schema["modules"]) if peak_mask & (1 << i)],
              "static_ceiling_MAC_per_cycle": 3392,
              "average_MAC_per_cycle": effective / latency,
              "average_to_static_ceiling_percent": effective / latency / 3392 * 100,
              "q_issue_windows": [int(row["last_issue"])-int(row["first_issue"])+1 for row in qrows],
              "q_start_intervals": [int(b["first_issue"])-int(a["first_issue"]) for a,b in zip(qrows,qrows[1:])],
              "module_layer_rows": layers, "aggregate": aggregate[0], "timeline": stage_analysis,
              "output_check": check, "mac_reconciliation": recon,
              "scope": "functional RTL at 3-ns simulation clock; not a board DDR-timing measurement"}
    (result / "accepted_rtl.json").write_text(json.dumps(output, indent=2))
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    result = args.result.resolve()
    result.mkdir(parents=True, exist_ok=False)
    state = {"version": "E07", "status": "PREPARING", "start": dt.datetime.now().astimezone().isoformat(), "frames": 1}
    def status(value):
        state["status"] = value
        (result / "status.json").write_text(json.dumps(state, indent=2))
        print(value, flush=True)
    status("PREPARING")
    helper_dir = WORKSPACE / "E04_weight_schedule/E05_attn_ln_token_pipeline/scripts"
    helper = load(helper_dir / "run_rtl_mac_activity.py", "e07_copy_helpers")
    full = load(helper_dir / "run_rtl_mac_activity_full.py", "e07_sim_helpers")
    rtl = ROOT / "hls/work/hls/syn/verilog"
    schema = discover_mac(rtl)
    (result / "signal_schema.json").write_text(json.dumps(schema, indent=2))
    (result / "identity.json").write_text(json.dumps({"version": "E07", "source_sha256": {p.name:sha(p) for p in (ROOT / "src").glob("*") if p.is_file()},
        "rtl_sha256": schema["rtl_sha256"], "input_sha256": {p.name:sha(p) for p in (ROOT / "inputs").glob("*") if p.is_file()},
        "observer_sha256": sha(Path(__file__)), "clock_period_ns": 3.0, "simulated_frames": 1}, indent=2))
    project = result / "project"
    (project / "hls").mkdir(parents=True)
    shutil.copytree(ROOT / "hls/work", project / "hls/work",
                    ignore=shutil.ignore_patterns("impl", "sim", "*.wdb", "xsim.dir"))
    config = project / "hls/hls_cosim_setup.cfg"
    config.write_text(setup_config(ROOT))
    status("NATIVE_COSIM_SETUP")
    with (result / "setup.log").open("x") as log:
        run = subprocess.run(["/opt/vivado/2025.1/Vitis/bin/vitis-run", "--mode", "hls", "--cosim", "--config", str(config), "--work_dir", "work"], cwd=config.parent, stdout=log, stderr=subprocess.STDOUT)
    if run.returncode:
        status("SETUP_FAILED")
        return run.returncode
    sim = project / "hls/work/hls/sim"
    tb = sim / "verilog/vit_block_top.autotb.v"
    before = tb.read_text()
    full.set_transaction_count(tb, 1)
    stage_code, stage_schema = stage_monitor(tb.read_text(), rtl)
    (result / "stage_schema.json").write_text(json.dumps(stage_schema, indent=2))
    helper.inject_monitor(tb, render_monitor(schema) + stage_code)
    (result / "testbench_delta.patch").write_text("".join(difflib.unified_diff(before.splitlines(True),tb.read_text().splitlines(True),fromfile="generated",tofile="E07_one_frame_observer")))
    shell = sim / "verilog/run_xsim.sh"
    shell.write_text(re.sub(r"\s+-(?:view|protoinst)\s+\S+", "", shell.read_text()).replace("-debug all", ""))
    (sim / "verilog/vit_block_top.tcl").write_text("run all\nquit\n")
    if {p.name:sha(p) for p in rtl.glob("*") if p.is_file()} != schema["rtl_sha256"]:
        raise ValueError("frozen RTL changed during setup")
    copied_rtl = project / "hls/work/hls/syn/verilog"
    if {p.name:sha(p) for p in copied_rtl.glob("*") if p.is_file()} != schema["rtl_sha256"]:
        raise ValueError("copied synthesis RTL identity changed")
    status("RTL_RUNNING")
    with (result / "rtl.log").open("x") as log:
        run = subprocess.run(["bash", "run_xsim.sh"], cwd=sim / "verilog", stdout=log, stderr=subprocess.STDOUT)
    state["rtl_exit_code"] = run.returncode
    log = (result / "rtl.log").read_text(errors="replace")
    if run.returncode or "1 / 1" not in log or "ERROR:" in log:
        status("RTL_FAILED_OR_INCOMPLETE")
        return 2
    status("ANALYZING")
    analyze(result, sim, schema, stage_schema, full, helper)
    state["end"] = dt.datetime.now().astimezone().isoformat()
    status("PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback
        traceback.print_exc()
        raise
