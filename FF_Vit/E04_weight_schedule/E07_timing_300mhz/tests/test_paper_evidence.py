"""Evidence safety: wrong version, timer arithmetic, hierarchy and overwrite errors."""
from pathlib import Path
import importlib.util
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    path = ROOT / "scripts" / f"{name}.py"
    assert path.exists(), f"missing evidence implementation: {path.name}"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_board_raw_ticks_not_truncated_printed_ns():
    mod = load_script("update_paper_e07")
    result = mod.board_metrics(99_990_005, 28_678_760, 100)
    assert result["fps"] == pytest.approx(348.6552591534641)
    assert result["ns_per_frame"] == pytest.approx(2_868_162.672859153)
    assert result["effective_gops"] == pytest.approx(869.1392547532872)
    with pytest.raises(ValueError):
        mod.board_metrics(99_990_005, 0, 100)


def test_docx_cannot_overwrite_input_or_existing_output(tmp_path):
    mod = load_script("update_paper_e07")
    source = tmp_path / "source.docx"
    source.write_bytes(b"unchanged source")
    with pytest.raises(FileExistsError):
        mod.require_new_output(source, source)
    output = tmp_path / "existing.docx"
    output.write_bytes(b"user document")
    with pytest.raises(FileExistsError):
        mod.require_new_output(source, output)
    assert source.read_bytes() == b"unchanged source"
    assert output.read_bytes() == b"user document"


def test_e06_rtl_evidence_must_not_be_accepted_as_e07():
    mod = load_script("update_paper_e07")
    with pytest.raises(ValueError):
        mod.accept_rtl({"version": "E06", "status": "PASS", "frame_latency_cycles": 833045})
    with pytest.raises(ValueError):
        mod.accept_rtl({"version": "E07", "status": "RUNNING", "frame_latency_cycles": 833045})


def test_hierarchy_discovers_changed_fu_number_and_rejects_ambiguity(tmp_path):
    mod = load_script("run_paper_rtl")
    (tmp_path / "vit_block_top.v").write_text(
        "module vit_block_top();\nvit_block_top_child changed_fu_99();\nendmodule\n")
    (tmp_path / "vit_block_top_child.v").write_text(
        "module vit_block_top_child();\nvit_block_top_leaf leaf_U0();\nendmodule\n")
    (tmp_path / "vit_block_top_leaf.v").write_text("module vit_block_top_leaf();\nendmodule\n")
    paths = mod.instance_paths(tmp_path)
    assert paths["vit_block_top_leaf"] == ["AESL_inst_vit_block_top.changed_fu_99.leaf_U0"]
    assert mod.unique_path(paths, "vit_block_top_leaf").endswith("changed_fu_99.leaf_U0")
    paths["vit_block_top_leaf"].append("AESL_inst_vit_block_top.other.leaf_U0")
    with pytest.raises(ValueError):
        mod.unique_path(paths, "vit_block_top_leaf")


def test_setup_config_is_generate_only_with_absolute_source_paths():
    mod = load_script("run_paper_rtl")
    cfg = mod.setup_config(ROOT)
    settings = dict(line.split("=", 1) for line in cfg.splitlines() if "=" in line)
    assert settings["cosim.setup"] == "1"
    assert settings["cosim.enable_dataflow_profiling"] == "0"
    assert settings["cosim.trace_level"] == "none"
    assert settings["clock"] == "3ns"
    assert settings["syn.top"] == "vit_block_top"
    for line in cfg.splitlines():
        if line.startswith(("tb.file=", "syn.file=")):
            assert Path(line.split("=", 1)[1]).is_absolute()


def test_e07_observer_resolves_real_head_tail_and_changed_top_hierarchy():
    mod = load_script("run_paper_rtl")
    schema = mod.discover_mac(ROOT / "hls/work/hls/syn/verilog")
    assert len(schema["modules"]) == 14
    by_name = {row["module"]: row for row in schema["modules"]}
    assert ".grp_dataflow_wrapper_fu_6443." in by_name["Q"]["hierarchy"]
    assert ".grp_task_run_head_fu_11440." in by_name["Head"]["hierarchy"]
    assert "icmp_ln411_fu_443_p2" in by_name["Head"]["issue_expression"]
    assert "ap_block_pp0_stage0_subdone" in by_name["Head"]["issue_expression"]
    assert "cache_window_sm_read" in by_name["Q"]["issue_expression"]
    assert "cache_window_sm_empty_n" in by_name["Q"]["issue_expression"]


def test_doc_export_with_empty_style_definitions_can_receive_native_tables():
    from docx import Document
    mod = load_script("update_paper_e07")
    doc = Document()
    for style in list(doc.styles):
        doc.styles._element.remove(style._element)
    assert hasattr(mod, "ensure_styles"), "source DOCX has no named style definitions"
    mod.ensure_styles(doc)
    doc.add_heading("E07 实测结果", 1)
    mod.table(doc, [["指标", "值"], ["FPS", "348.655"]], "结果表")
    assert doc.tables[0].cell(1,1).text == "348.655"


def test_module_efficiency_uses_explicit_issue_window_not_residence():
    mod = load_script("update_paper_e07")
    rows = [{"module":"Q", "logical_lanes":"512", "issue_count":"2",
             "first_issue":"10", "last_issue":"13", "observed_cycles":"999",
             "valid_MAC":"1024", "issued_MAC":"1024"},
            {"module":"Q", "logical_lanes":"512", "issue_count":"2",
             "first_issue":"100", "last_issue":"103", "observed_cycles":"999",
             "valid_MAC":"1024", "issued_MAC":"1024"}]
    result = mod.rtl_module_metrics(rows,1000)[0]
    assert result["issue_window_cycles"] == 8
    assert result["issue_window_utilization_percent"] == 50
    assert result["active_frame_percent"] == pytest.approx(.4)
    assert result["effective_MAC"] == 2048


def test_acceptance_rejects_peak_above_claimed_bound():
    mod = load_script("update_paper_e07")
    evidence = {"version":"E07","status":"PASS",
                "effective_MAC":mod.EFFECTIVE_MAC,"issued_MAC":mod.ISSUED_MAC,
                "output_check":{"status":"PASS"},
                "observed_peak_MAC_per_cycle":4000,"static_ceiling_MAC_per_cycle":3392}
    with pytest.raises(ValueError,match="static"):
        mod.accept_rtl(evidence)


def test_budget_annotations_do_not_retain_e06_constants(tmp_path):
    import csv
    mod = load_script("update_paper_e07")
    path = tmp_path / "E07_Frame_Cycle_Budget.csv"
    path.write_text("component,cycles,qualification\n12_Transformer_layers,732996,12 x 61075\nControl_gaps_and_boundary_offset,60,55 plus 2\n")
    mod.refresh_budget_annotations(path,{"canonical_native_frame_cycles":833147,
                                       "raw_to_native_boundary_offset_cycles":2})
    rows = list(csv.DictReader(path.open()))
    assert "61075" not in rows[0]["qualification"]
    assert "732996" in rows[0]["qualification"]
    assert "58" in rows[1]["qualification"]


def test_single_frame_limits_native_systemverilog_control_and_finish():
    mod = load_script("replay_paper_single_frame")
    original = "\n".join(["for(int i=0; i<3; i++) begin", "for(int i=0; i<3; i++) begin",
                          "for(int j=0; j<3; j=j+refm.ap_done_cnt) begin",
                          "for(int j=0; j<3; j=j+refm.ap_done_cnt) @refm.ap_done_for_nexttrans;"])
    patched = mod.limit_systemverilog_sequence(original)
    assert patched.count("<1;") == 4
    with pytest.raises(ValueError):
        mod.limit_systemverilog_sequence("no expected native loops")


def test_stream_handshake_observer_closes_after_first_native_done():
    mod = load_script("replay_paper_single_frame")
    code = mod.output_monitor()
    assert "o_stream_logits_TVALID && AESL_inst_vit_block_top.o_stream_logits_TREADY" in code
    assert "$fclose" in code
    assert "!eop_closed" in code


def test_native_unused_reference_warning_is_qualified_not_hidden():
    mod = load_script("update_paper_e07")
    warning = "UVM_ERROR ./svr/svr_master_sequence.sv(47) [CRITICAL WARNNING] Array input is set to stream interface and array data is not all used. If simulation fails, please check array size"
    result=mod.qualify_native_log(warning)
    assert result['unused_reference_vector_warnings'] == 1
    assert result['native_log_error_free'] is False
    with pytest.raises(ValueError):
        mod.qualify_native_log("UVM_ERROR unexpected data mismatch")
