#!/usr/bin/env python3
"""Correct both native TB frame limits; reuse prepared simulation, not HLS."""
from pathlib import Path
import argparse
import csv
import datetime as dt
import difflib
import importlib.util
import json
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def limit_systemverilog_sequence(text):
    patched,n = re.subn(r"(for\(int [ij]=0; [ij]<)3(;)",r"\g<1>1\2",text)
    if n != 4:
        raise ValueError(f"expected exactly four native control/finish loops, found {n}")
    return patched


def output_monitor():
    return '''
integer eop_fd, eop_count; reg eop_closed;
initial begin
  eop_fd=$fopen("E07_Logits_Handshakes.csv","w");
  $fwrite(eop_fd,"cycle,index,data,keep,strb,last\\n");
  eop_count=0; eop_closed=0;
end
always @(posedge AESL_clock) begin
  if(!eop_closed) begin
    if(AESL_inst_vit_block_top.o_stream_logits_TVALID && AESL_inst_vit_block_top.o_stream_logits_TREADY) begin
      $fwrite(eop_fd,"%0d,%0d,%h,%h,%h,%h\\n",clk_cnt,eop_count,
        AESL_inst_vit_block_top.o_stream_logits_TDATA,AESL_inst_vit_block_top.o_stream_logits_TKEEP,
        AESL_inst_vit_block_top.o_stream_logits_TSTRB,AESL_inst_vit_block_top.o_stream_logits_TLAST);
      eop_count=eop_count+1;
    end
    if(AESL_inst_vit_block_top.ap_done) begin
      $fflush(eop_fd); $fclose(eop_fd); eop_closed=1;
    end
  end
end
'''


def load_run():
    path=ROOT / "scripts/run_paper_rtl.py"
    spec=importlib.util.spec_from_file_location("e07_prepared_replay",path)
    mod=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=mod
    spec.loader.exec_module(mod)
    return mod


def check_output_handshakes(sim,full):
    suffixes={"data":"data_V","keep":"keep_V","strb":"strb_V","last":"last_V"}
    rows=list(csv.DictReader((sim/"verilog/E07_Logits_Handshakes.csv").open()))
    if len(rows)!=1000 or [int(r["index"]) for r in rows]!=list(range(1000)):
        raise ValueError("missing, repeated or extra output handshake")
    mismatches={}
    for field,suffix in suffixes.items():
        path=sim/"tv/cdatafile"/f"c.vit_block_top.autotvout_o_stream_logits_V_{suffix}.dat"
        section=full.transaction_zero(path)
        expected=[int(x,16) for x in re.findall(r"^\s*(0x[0-9a-fA-F]+)\s*$",section,re.M)]
        observed=[int(r[field],16) for r in rows]
        if observed!=expected:
            mismatches[field]=sum(a!=b for a,b in zip(observed,expected))+abs(len(observed)-len(expected))
    if mismatches:
        raise ValueError(f"output handshake comparison failed: {mismatches}")
    return {"status":"PASS","accepted_outputs":1000,"mismatches":mismatches,
            "scope":"posedge TVALID && TREADY; data/keep/strb/last compared to C transaction zero"}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--prepared",type=Path,required=True)
    p.add_argument("--result",type=Path,required=True)
    args=p.parse_args()
    previous=args.prepared.resolve();result=args.result.resolve()
    result.mkdir(parents=True,exist_ok=False)
    run=load_run()
    state={"version":"E07","status":"PREPARING","frames":1,
           "prepared_from":str(previous),"start":dt.datetime.now().astimezone().isoformat(),
           "reason":"first attempt limited Verilog reports but native SV sequence still drove three frames"}
    def status(value):
        state["status"]=value
        (result/"status.json").write_text(json.dumps(state,indent=2))
        print(value,flush=True)
    status("PREPARING")
    for name in ("identity.json","signal_schema.json","stage_schema.json"):
        shutil.copy2(previous/name,result/name)
    shutil.copy2(Path(__file__),result/Path(__file__).name)
    project=result/"project"
    shutil.copytree(previous/"project",project,
                    ignore=shutil.ignore_patterns("xsim.dir","*.wdb","*.log","*.jou","*.pb",
                                                  "*.performance.result.*","rtl.*.dat","E07_*.csv","e04_raw_events.csv"))
    sim=project/"hls/work/hls/sim"
    sequence=sim/"verilog/svtb/vit_block_top_subsys_test_sequence_lib.sv"
    before=sequence.read_text();after=limit_systemverilog_sequence(before)
    sequence.write_text(after)
    helper_dir=run.WORKSPACE/"E04_weight_schedule/E05_attn_ln_token_pipeline/scripts"
    helper=run.load(helper_dir/"run_rtl_mac_activity.py","e07_fixed_helpers")
    full=run.load(helper_dir/"run_rtl_mac_activity_full.py","e07_fixed_full")
    tb=sim/"verilog/vit_block_top.autotb.v"
    tb_before=tb.read_text()
    if "parameter AUTOTB_TRANSACTION_NUM = 1;" not in tb_before:
        raise ValueError("Verilog frame-report limit is not one")
    helper.inject_monitor(tb,output_monitor())
    delta="".join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile="native_sequence",tofile="one_frame_sequence"))
    delta+="".join(difflib.unified_diff(tb_before.splitlines(True),tb.read_text().splitlines(True),fromfile="prepared_observer",tofile="one_frame_output_observer"))
    (result/"single_frame_delta.patch").write_text(delta)
    (result/"replay_identity.json").write_text(json.dumps({"native_sequence_sha256":run.sha(sequence),
            "testbench_sha256":run.sha(tb),"replay_script_sha256":run.sha(Path(__file__)),
            "delta_sha256":run.sha(result/"single_frame_delta.patch"),"frames":1},indent=2))
    status("RTL_RUNNING")
    with (result/"rtl.log").open("x") as log:
        proc=subprocess.run(["bash","run_xsim.sh"],cwd=sim/"verilog",stdout=log,stderr=subprocess.STDOUT)
    state["rtl_exit_code"]=proc.returncode
    log=(result/"rtl.log").read_text(errors="replace")
    if proc.returncode or "1 / 1" not in log or "ERROR:" in log or "Simulator command interrupted" in log:
        status("RTL_FAILED_OR_INCOMPLETE")
        return 2
    status("ANALYZING")
    check=check_output_handshakes(sim,full)
    shutil.copy2(sim/"verilog/E07_Logits_Handshakes.csv",result/"E07_Logits_Handshakes.csv")
    (result/"output_handshake_check.json").write_text(json.dumps(check,indent=2))
    schema=json.loads((result/"signal_schema.json").read_text())
    stage=json.loads((result/"stage_schema.json").read_text())
    run.analyze(result,sim,schema,stage,full,helper)
    state["end"]=dt.datetime.now().astimezone().isoformat()
    status("PASS")
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback
        traceback.print_exc()
        raise
