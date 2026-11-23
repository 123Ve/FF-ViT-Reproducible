#!/usr/bin/env python3
"""Create an evidence-labelled E07 Word copy; never overwrite source or outputs."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import shutil
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.style import WD_STYLE_TYPE
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]
EVIDENCE = ROOT / "results/paper_evidence"
EFFECTIVE_MAC = 1_246_416_384
ISSUED_MAC = 1_246_563_840


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def board_metrics(timer_hz, ticks, frames):
    if min(timer_hz, ticks, frames) <= 0:
        raise ValueError("timer, ticks and frames must be positive")
    seconds = ticks / timer_hz
    fps = frames / seconds
    return {"frames": frames, "ticks": ticks, "timer_hz": timer_hz,
            "total_seconds": seconds, "ns_per_frame": seconds / frames * 1e9,
            "fps": fps, "effective_gmac_s": EFFECTIVE_MAC * fps / 1e9,
            "effective_gops": 2 * EFFECTIVE_MAC * fps / 1e9}


def require_new_output(source, output):
    if source.resolve() == output.resolve() or output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")


def accept_rtl(data):
    if data.get("version") != "E07" or data.get("status") != "PASS":
        raise ValueError("only completed, explicitly identified E07 RTL is accepted")
    if data.get("effective_MAC") != EFFECTIVE_MAC or data.get("issued_MAC") != ISSUED_MAC:
        raise ValueError("RTL work reconciliation missing or invalid")
    if data.get("output_check", {}).get("status") != "PASS":
        raise ValueError("RTL logits/AXIS validation missing")
    if data.get("observed_peak_MAC_per_cycle", 0) > data.get("static_ceiling_MAC_per_cycle", 0):
        raise ValueError("observed peak exceeds claimed static bound; rederive concurrency before publishing")
    per_layer = {"Q":14112,"K":14112,"V":14112,"O":12544,
                 "MLP1":28224,"MLP2":28224,
                 **{f"{stage}{head}":9604 for stage in ("QK","AV") for head in range(3)}}
    for module,expected in per_layer.items():
        selected = [r for r in data.get("module_layer_rows",[]) if r["module"] == module]
        if len(selected) != 12 or {int(r["layer"]) for r in selected} != set(range(12)):
            raise ValueError(f"incomplete per-layer attribution for {module}")
        if any(int(r["issue_count"]) != expected for r in selected):
            raise ValueError(f"per-layer MAC count mismatch for {module}")
    return data


def rtl_module_metrics(rows, frame_cycles):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["module"]].append(row)
    result = []
    for name, selected in grouped.items():
        lanes = {int(row["logical_lanes"]) for row in selected}
        if len(lanes) != 1 or frame_cycles <= 0:
            raise ValueError("inconsistent module lanes or frame boundary")
        lanes = lanes.pop()
        windows = sum(int(r["last_issue"])-int(r["first_issue"])+1 for r in selected)
        active = sum(int(r["issue_count"]) for r in selected)
        effective = sum(int(r["valid_MAC"]) for r in selected)
        issued = sum(int(r["issued_MAC"]) for r in selected)
        if windows <= 0 or active > windows:
            raise ValueError("invalid accepted-issue window")
        result.append({"module":name,"logical_lanes":lanes,
                       "issue_window_cycles":windows,"active_cycles":active,
                       "effective_MAC":effective,"issued_MAC":issued,
                       "issue_window_utilization_percent":effective/(lanes*windows)*100,
                       "active_frame_percent":active/frame_cycles*100})
    return result


def refresh_budget_annotations(path, timeline):
    """Replace inherited prose constants, not independently measured cycles."""
    with path.open() as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        rows = list(reader)
    for row in rows:
        if row["component"] == "12_Transformer_layers":
            row["qualification"] = f"sum of 12 sequential E07 layer-task windows = {row['cycles']} cycles"
        elif row["component"] == "Control_gaps_and_boundary_offset":
            offset = int(timeline["raw_to_native_boundary_offset_cycles"])
            row["qualification"] = f"{int(row['cycles'])-offset} raw control-gap cycles plus {offset} observer/native boundary cycles"
    with path.open("w",newline="") as f:
        writer = csv.DictWriter(f,fieldnames=columns)
        writer.writeheader(); writer.writerows(rows)


def qualify_native_log(text):
    errors=[line for line in text.splitlines() if line.startswith("UVM_ERROR")]
    known=[line for line in errors if "svr_master_sequence.sv(47)" in line
           and "array data is not all used" in line]
    if len(errors)!=len(known) or "UVM_FATAL " in text or "ERROR:" in text:
        raise ValueError("unexpected native simulation error; do not publish")
    return {"unused_reference_vector_warnings":len(known),
            "native_log_error_free":not errors,
            "qualification":"SV control completes one frame; retained C TV files contain three frames. Native transaction-zero outputs and independent 1000-handshake comparison pass. This is not claimed as a warning-free log.",
            "messages":known}


def qualify_rtl_outputs(path, rtl):
    result=path.parent
    qualification=qualify_native_log((result/"rtl.log").read_text(errors="replace"))
    if json.loads((result/"output_handshake_check.json").read_text()).get("status")!="PASS":
        raise ValueError("independent output handshake check did not pass")
    reference=result/"project/hls/work/hls/sim/tv/cdatafile/c.vit_block_top.autotvin_i_stream_ext_V_data_V.dat"
    if qualification['unused_reference_vector_warnings'] and reference.read_text().count('[[transaction]]')!=3:
        raise ValueError("unused-vector warning does not have the expected three-frame reference explanation")
    original=result/"accepted_rtl_native_analysis.json"
    if not original.exists():
        shutil.copy2(path,original)
    rtl['log_qualification']=qualification
    rtl['timeline']['axi_all']={key:int(rtl['aggregate'][key])
                               for key in ('axi_ar_requests','axi_requested_bytes','axi_r_beats')}
    rtl['timeline']['axi_all']['scope']='whole-frame gmem_w aggregate; per-layer AXI activity not collected'
    csv_path=result/"E07_RTL_Layer_Timeline.csv"
    backup=result/"E07_RTL_Layer_Timeline_native_analysis.csv"
    if not backup.exists():
        shutil.copy2(csv_path,backup)
    with csv_path.open() as f:
        reader=csv.DictReader(f);columns=reader.fieldnames;rows=list(reader)
    for row in rows:
        for key in columns:
            if key.startswith('axi_') or key in ('first_axi_cycle','last_axi_cycle'):
                row[key]='NOT_COLLECTED'
    with csv_path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(rows)
    path.write_text(json.dumps({k:v for k,v in rtl.items() if k!='_result_dir'},indent=2))
    (result/'native_log_qualification.json').write_text(json.dumps(qualification,indent=2))


def hls_metrics():
    report = ROOT / "hls/work/hls/syn/report"
    specs = [
        ("Patch（有效）", "fixed_patch_step2_mac_replace_shift", 28_753_920, 576, "一帧；不计替换掉的 token 0"),
        ("Patch（issued）", "fixed_patch_step2_mac_replace_shift", 28_901_376, 576, "一帧；含 token 0 冗余投影"),
        ("Q", "do_matmul_2", 7_225_344, 512, "每层每个独立投影"),
        ("K", "do_matmul_2_1", 7_225_344, 512, "每层每个独立投影"),
        ("V", "do_matmul_4", 7_225_344, 512, "每层每个独立投影"),
        ("QK", "do_attn_6_Pipeline_PASS1_J_LOOP", 25_088, 256, "一个 Head、一个 TP=2 查询对"),
        ("AV", "do_attn_6_Pipeline_PASS3_J_LOOP", 25_088, 256, "一个 Head、一个 TP=2 查询对"),
        ("O", "do_matmul_1", 7_225_344, 576, "每层完整投影"),
        ("MLP1", "do_matmul_3", 28_901_376, 1024, "每层 196×192×768"),
        ("MLP2", "do_matmul", 28_901_376, 1024, "每层 196×768×192"),
        ("Head", "fixed_head_matmul_core", 192_000, 8, "一个 CLS 向量，非 196 次分类"),
        ("Attention LN", "do_layernorm_inter_token_1", None, None, "非模型 MAC"),
        ("Softmax Pass 2", "do_attn_6_Pipeline_PASS2_J_LOOP", None, None, "一个 Head、一个查询对"),
        ("MLP LN", "do_layernorm_inter_token", None, None, "非模型 MAC"),
        ("GeLU", "do_gelu", None, None, "非模型 MAC"),
        ("Attention 残差加", "stream_merge", None, None, "非模型 MAC"),
        ("MLP 残差加", "stream_merge_1", None, None, "非模型 MAC"),
    ]
    result = []
    for name, suffix, mac, lanes, boundary in specs:
        p = report / (suffix + "_csynth.xml")
        xml = ET.parse(p).getroot()
        summary = xml.find(".//SummaryOfOverallLatency")
        latency = int(summary.findtext("Worst-caseLatency"))
        interval = int(summary.findtext("Interval-max"))
        result.append({"module": name, "function": suffix, "MAC": mac, "lanes": lanes,
                       "latency": latency, "interval": interval, "boundary": boundary,
                       "eta_latency": mac / lanes / latency * 100 if mac else None,
                       "eta_interval": mac / lanes / interval * 100 if mac else None,
                       "evidence_class": "HLS_ESTIMATE", "report": str(p.relative_to(WORKSPACE)),
                       "sha256": sha(p)})
    return result


def bram_category(cell):
    # Post-route instance-name attribution; unidentified renamed cells stay explicit.
    rules = [
        ("层权重乒乓缓存", "pp_bram_"),
        ("Patch 投影权重", "PATCH_WEIGHT"),
        ("位置相关 Patch bias", "PATCH_BIAS"),
        ("Head 权重", "HEAD_WEIGHT"),
        ("层间 Feature-map 乒乓缓存", "p_ZZ13vit_block_top"),
        ("Q/K/V 激活缓存", "Q_buf"),
        ("Q/K/V 激活缓存", "K_buf"),
        ("Q/K/V 激活缓存", "V_buf"),
        ("Attention 分数缓存", "S_buf"),
        ("专用残差缓存", "resi"),
        ("Attention/MLP LN 双缓冲", "buffer_ping"),
        ("Attention/MLP LN 双缓冲", "buffer_pong"),
        ("MatMul 输入/窗口缓存", "matmul_step1_cache_window"),
        ("Patch 输入适配缓存", "adpt_sm"),
        ("AXI/DMA 接口 FIFO", "axi_dma"),
        ("AXI/DMA 接口 FIFO", "gmem_w_m_axi"),
        ("Head LN 输入缓存", "fixed_head_layernorm_U0/buffer_U"),
        ("Head MatMul 输入缓存", "fixed_head_matmul_core_U0/wb_U"),
    ]
    if "HEAD_BIAS" in cell:
        return "Head 偏置 ROM" if "_U/q0_reg" in cell else "实现后流水/延迟对齐存储"
    for category, pattern in rules:
        if pattern in cell:
            return category
    if "reg_rep" in cell:
        return "实现后流水/延迟对齐存储"
    return "实现后改写、尚未唯一归因"


def bram_metrics():
    groups = defaultdict(Counter)
    inventory = []
    with (EVIDENCE / "E07_BRAM_Cells.csv").open() as f:
        for row in csv.DictReader(f):
            row["category"] = bram_category(row["cell"])
            groups[row["category"]][row["primitive"]] += 1
            inventory.append(row)
    result = [{"category": k, "RAMB36E2": n["RAMB36E2"], "RAMB18E2": n["RAMB18E2"],
               "tiles": n["RAMB36E2"] + n["RAMB18E2"] / 2} for k,n in groups.items()]
    if sum(r["RAMB36E2"] for r in result) != 324 or sum(r["RAMB18E2"] for r in result) != 362:
        raise ValueError("post-route BRAM inventory does not match native utilization report")
    with (EVIDENCE / "E07_BRAM_Classified.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["cell", "primitive", "category"])
        w.writeheader(); w.writerows(inventory)
    return result


def save_csv(name, rows):
    with (EVIDENCE / name).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)


def ensure_styles(doc):
    definitions = [("Normal",WD_STYLE_TYPE.PARAGRAPH),
                   ("Heading 1",WD_STYLE_TYPE.PARAGRAPH),
                   ("Caption",WD_STYLE_TYPE.PARAGRAPH),
                   ("Table Grid",WD_STYLE_TYPE.TABLE)]
    for name,kind in definitions:
        if name not in doc.styles:
            style = doc.styles.add_style(name,kind)
            if kind == WD_STYLE_TYPE.PARAGRAPH and name != "Normal":
                style.base_style = doc.styles["Normal"]
            if name == "Heading 1":
                style.font.size = Pt(14)
                style.font.bold = True
                style.paragraph_format.keep_with_next = True
                style.paragraph_format.space_before = Pt(12)
            if kind == WD_STYLE_TYPE.TABLE:
                borders = OxmlElement("w:tblBorders")
                for edge in ("top","left","bottom","right","insideH","insideV"):
                    node=OxmlElement("w:"+edge)
                    node.set(qn("w:val"),"single"); node.set(qn("w:sz"),"4")
                    node.set(qn("w:color"),"A0A0A0"); borders.append(node)
                props=OxmlElement("w:tblPr"); props.append(borders)
                style._element.append(props)


def table(doc, rows, title=None):
    if title:
        caption = doc.add_paragraph(title, style="Caption")
        caption.paragraph_format.keep_with_next = True
    tbl = doc.add_table(rows=0, cols=len(rows[0]))
    tbl.style = "Table Grid"
    tbl.autofit = False
    for index, values in enumerate(rows):
        cells = tbl.add_row().cells
        for cell,value in zip(cells,values):
            cell.text = str(value)
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.space_before = Pt(2)
                for run in p.runs:
                    run.font.size = Pt(9)
                    run.font.name = "Arial"
                    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "Noto Sans CJK SC")
                    if index == 0:
                        run.bold = True
        if index == 0:
            trpr = tbl.rows[index]._tr.get_or_add_trPr()
            repeat = OxmlElement("w:tblHeader"); trpr.append(repeat)
            for cell in cells:
                shade = OxmlElement("w:shd"); shade.set(qn("w:fill"), "E8EEF5")
                cell._tc.get_or_add_tcPr().append(shade)
        trpr = tbl.rows[index]._tr.get_or_add_trPr()
        trpr.append(OxmlElement("w:cantSplit"))
    return tbl


def extract_source_tables(source):
    tables = {}
    with ZipFile(source) as z:
        for i in range(1,21):
            wb = load_workbook(BytesIO(z.read(f"word/embeddings/Microsoft_Excel_Worksheet{i}.xlsx")), data_only=True)
            tables[str(i)] = [list(row) for row in wb.active.iter_rows(values_only=True) if any(v is not None for v in row)]
    (EVIDENCE / "source_E06_embedded_tables.json").write_text(json.dumps(tables, ensure_ascii=False, indent=2))
    return tables


def replace_hardware_section(doc):
    body = doc._element.body
    nodes = list(body)
    begin = next(i for i,n in enumerate(nodes) if "二、资源基线" in "".join(n.itertext()))
    removed_relations = set()
    for node in nodes[begin:]:
        if node.tag == qn("w:sectPr"):
            continue
        for element in node.iter():
            for key,value in element.attrib.items():
                if key.startswith("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"):
                    removed_relations.add(value)
        body.remove(node)
    remaining = {v for el in body.iter() for k,v in el.attrib.items()
                 if k.startswith("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}")}
    for rid in removed_relations - remaining:
        if rid in doc.part.rels:
            doc.part.drop_rel(rid)
    doc.paragraphs[0].text = "论文修改——E07 300-MHz 时序优化版"


def create_document(source, output, evidence, rtl=None):
    require_new_output(source, output)
    source_digest = sha(source)
    doc = Document(source)
    ensure_styles(doc)
    replace_hardware_section(doc)
    style = doc.styles["Normal"]
    style.font.name = "Arial"; style.font.size = Pt(10.5)
    style._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "Noto Sans CJK SC")
    style.paragraph_format.space_after = Pt(5)
    for s in doc.sections:
        s.page_width = Cm(21); s.page_height = Cm(29.7)
        s.left_margin = s.right_margin = Cm(2)
    board = evidence["board"]
    hz = evidence["pl_mhz"] * 1e6
    bram = evidence["bram"]
    by_bram = {r["category"]:r for r in bram}
    note = lambda text: doc.add_paragraph(text)
    doc.add_page_break()
    doc.add_heading("二、E07 实现资源与版本身份", 1)
    note("本文硬件主结果统一采用 E07：196-token、12 层整数 FF-ViT，器件为 XCZU9EG-FFVB1156-2-E，平台为 ZCU102。E06 的源码、RTL、权重和上板文件保持冻结，原 Word 文档亦未覆盖。量化及数据集结果保留原版本；时序优化并未重新训练模型，板级逐位检查不能替代数据集 Top-1 评测。")
    note("证据标签：BOARD_MEASURED 为用户提供的板级 UART；POST_ROUTE 为最终实现网表/时序报告；HLS_ESTIMATE 为 HLS 综合报告；RTL_OBSERVATION 为独立只读 RTL 回放；DERIVED 为按明确公式换算；待测项不使用 E06 数字代填。")
    table(doc, [["项目", "E07 数值", "利用率/说明", "证据"],
                ["PL 配置频率", f"{evidence['pl_mhz']:.6f} MHz", "MMCM；非晶振实测频率", "POST_ROUTE / UART"],
                ["LUT", "218,759", "79.82%", "POST_ROUTE"],
                ["FF", "188,403", "34.37%", "POST_ROUTE"],
                ["CLB sites", "33,817 / 34,260", "98.71%；不等同于 LUT 利用率", "POST_ROUTE"],
                ["DSP48E2", "736", "29.21%", "POST_ROUTE"],
                ["BRAM36 等效", "505.0 tiles", "55.37%", "POST_ROUTE"],
                ["RAMB36E2 / RAMB18E2", "324 / 362", "324 + 362/2 = 505", "POST_ROUTE"],
                ["WNS / TNS", "+0.023 / 0.000 ns", "setup 闭合，余量仅 23 ps", "POST_ROUTE"],
                ["WHS / THS", "+0.010 / 0.000 ns", "hold 闭合", "POST_ROUTE"],
                ["HLS 目标/估计周期", "3.000 / 3.016 ns", "不是布局布线后的 Fmax", "HLS_ESTIMATE"]], "表 1　E07 最终布局布线结果")
    note("已验证的工作点为配置频率 300.215099 MHz，不能将其表述为已扫描得到的最大 Fmax。仅按 3.331 ns 周期减去 0.023 ns setup slack 粗略换算约 302.30 MHz，属于局部时序推算，不代表该频率重新实现或上板通过。")
    table(doc, [["存储类别", "RAMB36E2", "RAMB18E2", "BRAM36 等效", "占整机"],
                *[[r['category'],r['RAMB36E2'],r['RAMB18E2'],f"{r['tiles']:.1f}",f"{r['tiles']/505*100:.3f}%"] for r in bram],
                ["合计",324,362,"505.0","100.000%"]], "表 2　E07 实现后 BRAM 互斥分类")
    note("分类由最终 checkpoint 中的 RAMB 实例名逐项归属并对账；实现后改名且尚未唯一归因的单元单独保留，不能强行归入 LUT 表。BRAM36 等效不是逻辑容量：分区、端口、宽深比和实现后重写都会影响物理数量。自动流水存储不重复计入权重、激活或残差分类。")
    table(doc, [["双缓冲结构", "实际物理占用", "第二份的等效开销", "说明"],
                ["层权重缓存",f"{by_bram['层权重乒乓缓存']['tiles']:.1f} tiles",f"{by_bram['层权重乒乓缓存']['tiles']/2:.1f} tiles","按两个逻辑 Bank 对称折半；未做移除 Bank 的反事实实现"],
                ["Feature-map 缓存",f"{by_bram['层间 Feature-map 乒乓缓存']['tiles']:.1f} tiles",f"{by_bram['层间 Feature-map 乒乓缓存']['tiles']/2:.1f} tiles","亦作为 Attention 残差的数据来源"],
                ["Attention+MLP LN",f"{by_bram['Attention/MLP LN 双缓冲']['tiles']:.1f} tiles","1.0 tile","跨 token-pair 的统计/归一化重叠"]], "表 3　双缓冲相关存储（是表 2 的子集，不再相加）")
    doc.add_heading("三、并行度与 MAC 资源效率", 1)
    table(doc, [["算子", "CI/CIP", "CO/COP", "TP", "逻辑 MAC 通道"],
                ["Patch","768/24","192/12",2,576],
                ["Q / K / V（各自）","192/16","192/16",2,512],
                ["QK（每 Head）","2 queries × 2 keys × 64 channels","—",2,256],
                ["AV（每 Head）","2 queries × 2 keys × 64 channels","—",2,256],
                ["O","192/24","192/12",2,576],
                ["MLP1","192/16","768/32",2,1024],
                ["MLP2","768/32","192/16",2,1024],
                ["Head","192/1","1000/8",1,8]], "表 4　E07 逻辑并行度（与物理 DSP 数量不同）")
    note("已安装逻辑 MAC 通道总数为 6,280，但不能同时有效计算。QK 与 AV 在同一 Head 中按三 Pass 顺序执行，三 Head 共至多 768 条 Attention MAC 通道；Q/K/V 加载与完整 Attention 计算存在缓存阶段约束，Patch、12 层 backbone 和 Head 也由顶层控制串行调用。结合已核实的 RTL 控制与未改变的算法调度，静态并发上界为 3,392 MAC/cycle；这不是观测峰值。该上界在 E07 回放中另外检查同 Head QK/AV 不重叠。")
    note("E07 将 Head 的 8 条乘法通道绑定到 DSP，并因更紧时钟目标增加流水级，但没有扩张 MAC 阵列。736 是物理 DSP48E2 总数，包含模型计算和辅助算术；不能写成 736 个有效模型 MAC/cycle。E06 的 DSP-bound/fabric multiplier 数量不在未完成 E07 逐单元绑定审计的情况下照搬。")
    table(doc, [["模块/边界", "MAC/调用", "P", "HLS latency", "HLS interval", "η_latency", "η_interval"],
                *[[r['module'],f"{r['MAC']:,}" if r['MAC'] else "非 MAC",r['lanes'] or "—",r['latency'],r['interval'],
                   f"{r['eta_latency']:.3f}%" if r['eta_latency'] is not None else "未定义",
                   f"{r['eta_interval']:.3f}%" if r['eta_interval'] is not None else "未定义"] for r in evidence['hls']]], "表 5　E07 算子调用边界的 HLS 效率（估计，不是板级活动）")
    note("η_HLS,latency = MAC/调用 ÷ (P × HLS function latency)；η_HLS,interval 用完整函数启动 interval 作分母，两者不混用。QK/AV 按每 Head、每查询对统计，矩阵投影按完整层统计。叶循环 II=1 不意味着整层或整帧 II=1；非模型 MAC 算子的 MAC 效率未定义，而不是零。")
    board_ratio = board['effective_gmac_s'] * 1e9 / (hz*3392)*100
    if rtl:
        table(doc, [["指标", "E07 数值", "证据"],
                    ["单帧 effective / issued MAC",f"{rtl['effective_MAC']:,} / {rtl['issued_MAC']:,}","RTL 对账通过"],
                    ["完整帧 RTL 周期",f"{rtl['frame_latency_cycles']:,}","原生 transaction report"],
                    ["平均 effective MAC/cycle",f"{rtl['average_MAC_per_cycle']:.3f}","RTL_DERIVED"],
                    ["观测峰值 MAC/cycle",rtl['observed_peak_MAC_per_cycle'],"RTL_OBSERVATION"],
                    ["峰值时并发模块",", ".join(rtl['observed_peak_modules']),"RTL_OBSERVATION"],
                    ["静态理论并发上界",3392,"STATIC_ANALYSIS"],
                    ["帧平均/静态上界",f"{rtl['average_to_static_ceiling_percent']:.3f}%","RTL_DERIVED"],
                    ["板级端到端速率/静态上界",f"{board_ratio:.3f}%","BOARD_DERIVED；不是模块利用率"],
                    ["跨帧 RTL 启动间隔", "单帧无法测量", "不等同于层启动间隔"]], "表 6　整机 RTL 计算效率与板级口径区分")
        module_metrics = rtl_module_metrics(rtl['module_layer_rows'],rtl['frame_latency_cycles'])
        table(doc, [["模块", "P", "有效 ISSUE cycles", "ISSUE 窗口和", "effective MAC", "窗口效率", "整帧活动比例"],
                    *[[r['module'],r['logical_lanes'],f"{r['active_cycles']:,}",f"{r['issue_window_cycles']:,}",
                       f"{r['effective_MAC']:,}",f"{r['issue_window_utilization_percent']:.3f}%",f"{r['active_frame_percent']:.3f}%"]
                      for r in module_metrics]], "表 6a　E07 模块有效发射活动（单帧 RTL）")
        note("表 6a 的窗口是每层该模块首次至末次有效 ISSUE 的 inclusive 区间，随后对 12 层求和；Patch/Head 各一个窗口。它包括发射间隙，但不包括首次发射前和末次发射后的 fill/drain，因而不是 ap_start→ap_done 驻留窗口利用率，亦不是表 5 的 HLS 调用效率。活动比例为接受 ISSUE 的周期数/完整帧周期；不同模块的活动可重叠，不能相加作为帧周期预算。QK/AV 逐 Head 分列，窗口含该阶段各查询对之间的间隙。")
    else:
        table(doc, [["指标", "E07 数值/状态", "证据"],
                    ["单帧 effective / issued 工作量",f"{EFFECTIVE_MAC:,} / {ISSUED_MAC:,}","模型/源码预期，RTL 待对账"],
                    ["完整 RTL 周期、峰值及 MAC 利用率","单帧只读回放进行中","不沿用 E06 的 833,045 / 3,136 / 44.110%"],
                    ["静态理论并发上界",3392,"STATIC_ANALYSIS"],
                    ["板级端到端速率/静态上界",f"{board_ratio:.3f}%","BOARD_DERIVED；不是 RTL 利用率"]], "表 6　整机计算效率的现有证据状态")
    note("有效与 issued 相差 147,456 MAC，即一个 Patch token 的 768×192 冗余投影；位置 0 随后由 CLS 向量替换。这不是 padding，也不能把冗余计算计入有效模型吞吐量。静态上界按配置频率换算为约 2,036.659 GOP/s（1 MAC=2 operations），须与板级端到端有效吞吐量分列。")
    note("有效 MAC 是根据已核实的接受 ISSUE 事件与有效逻辑通道数换算的模型 MAC 等效量，不是每个 DSP/LUT 单元的开关活动。帧平均/静态上界反映时间忙闲和模块并发的综合效果，不等同于全部 6,280 条已安装通道的物理同时占用率，也不能替代实测功耗。")
    doc.add_heading("四、完整帧周期与板级测量协议", 1)
    table(doc, [["指标", "E07 结果", "测量范围"],
                ["计时器频率","99,990,005 Hz","PS timer，非 PL cycle counter"],
                ["正式计时帧数",100,"2 帧预热不在计时窗口内"],
                ["原始 timer delta","28,678,760 ticks","用户提供的 UART"],
                ["100 帧总时间",f"{board['total_seconds']*1000:.6f} ms","由原始 ticks 计算"],
                ["平均单帧时间",f"{board['ns_per_frame']/1e6:.6f} ms","端到端串行平均"],
                ["串行帧率",f"{board['fps']:.6f} FPS","完成帧数/总墙钟时间"],
                ["有效吞吐量",f"{board['effective_gmac_s']:.6f} GMAC/s","按 effective MAC/frame 换算"],
                ["2 operations/MAC",f"{board['effective_gops']:.6f} GOP/s","有效端到端吞吐量"],
                ["输出一致性","预热后 1,000 logits，mismatches=0","快速固件不逐帧核查计时的 100 帧"],
                ["独立计时批次数/方差","1 批；方差不可得","不能假称 10 次重复或 1,000 帧"],
                ["跨帧重叠","无","每帧完成后启动下一帧"]], "表 7　E07 板级快速测量结果")
    note("计时包括逐帧 cache 操作、PS 调度、输入 DDR→DMA→PL、完整推理、输出 PL→DMA→DDR 及完成轮询；不包含初始 SD 文件读取、一次性输入打包和两帧预热。FPS 与平均帧时间互为倒数是串行帧协议的结果，不代表跨帧流水吞吐。原始 timer delta 优先于 UART 截断后的整数 ns。100 次重复同一输入不等价于 100 张独立验证集图像。")
    note("此快速固件在预热后、正式计时前逐位核查 1,000 个 logits；计时的 100 帧包含输出 DMA 完成、ap_done 轮询和 cache invalidate，但不包含逐帧读取全部 logits 并与参考逐位比较的开销。mismatches=0 的验证范围与 FPS 的计时范围分别报告。")
    note("本测试是输入已预加载的板侧加速器基准，不包含主机/网络上传及云端交互时间；不能将此 FPS 改称 IoT 云端端到端吞吐量。")
    if rtl:
        native = rtl['frame_latency_cycles']
        rtl_result = Path(rtl['_result_dir'])
        from_file = rtl_result / "E07_Frame_Cycle_Budget.csv"
        with from_file.open() as f:
            budget = list(csv.DictReader(f))
        table(doc, [["非重叠顶层阶段", "RTL cycles", "完整帧占比"],
                    *[[r['component'],r['cycles'],f"{float(r['percent_of_native_frame']):.3f}%"] for r in budget],
                    ["完整帧",f"{native:,}","100.000%"]], "表 8　E07 完整帧 RTL 协调周期预算")
        timeline = rtl['timeline']
        with (rtl_result / "E07_RTL_Layer_Timeline.csv").open() as f:
            lr = list(csv.DictReader(f))
        table(doc, [["层内观察量", "E07 cycles", "定义"],
                    ["Layer wrapper",", ".join(map(str,sorted({int(r['layer_cycles']) for r in lr}))),"逐层 start→done"],
                    ["层 Q 发射启动间隔",", ".join(map(str,sorted(set(rtl['q_start_intervals'])))),"相邻层 Q 首次 ISSUE 之差"],
                    ["Q/K/V 每层 ISSUE 窗口",", ".join(map(str,sorted(set(rtl['q_issue_windows'])))),"此行列 Q，inclusive first→last；K/V 明细另存"],
                    *[[k,", ".join(map(str,sorted({int(r[col]) for r in lr}))),"并行任务驻留窗口；不可相加"] for k,col in [("Attention","attention_cycles"),("MLP","mlp_cycles"),("Feature-map 写回","write_fm_cycles")]]], "表 9　层内重叠任务与发射窗口")
        table(doc, [["量", "E07 RTL cycles", "边界"],
                    *[[key,f"{timeline[key]:,}",desc] for key,desc in [
                        ("weight_load_cycles","W0–W11 有效加载窗口并集"),
                        ("compute_cycles","Patch/Attention/MLP/写回/Head 驻留窗口并集"),
                        ("overlap_cycles","有效加载与上述计算窗口的交集"),
                        ("compute_wait_weight_cycles","所需权重晚于当前层 start 就绪的正差")]]], "表 10　E07 权重预取与计算窗口对账")
        note("Attention、MLP 和写回在流上重叠，不能将三个任务周期相加；HLS 函数 latency 也不能直接相乘得到完整帧。compute_cycles 含 LN、Softmax、GeLU、fill/drain 与控制，并不是纯 MAC 活跃周期。加载窗口覆盖率按 overlap_cycles/weight_load_cycles 定义；它不是 DDR beat-active 与 MAC 有效周期的重叠率。")
        note("RTL 周期来自指定 AXI 仿真内存模型，板级时间包含真实 DDR、DMA、PS 与软件开销。将 RTL cycles 按配置频率换算后与板级 ms 作对比可以检查数量级，但差值不能直接全部归因于 PS 或 DMA，也不能据此推得板级逐模块计算时间。")
    else:
        note("E07 顶层 HLS 的最坏延迟为 undef，不能以其子任务约 49k cycles 代替完整帧周期；也不能把板级 2.868 ms 乘 PL 频率反推成纯 RTL latency。阶段周期预算、层间隔和权重重叠等待此次单帧完成后补入。")
    doc.add_heading("五、196-token、CLS、位置参数和残差存储", 1)
    note("硬件序列 N=196，TP=2 对应 98 个查询/输入 token-pair。位置 0 的投影先发射后被 PATCH_CLS_BANK 替换，其余 195 个位置保留 Patch 投影。PATCH_BIAS_BANK 的逻辑尺寸为 196×192，用于位置和通道相关加性参数。不能未经模型侧确认，把该硬件称为标准 197-token DeiT 序列；模型位置嵌入的训练/裁剪来源沿用原有确认范围，不由时序实验推断。")
    table(doc, [["结构", "逻辑尺寸/精度", "E07 物理占用", "作用"],
                ["PATCH_BIAS_BANK","196×192",f"{by_bram['位置相关 Patch bias']['tiles']:.1f} tiles","位置相关加性参数 ROM"],
                ["PATCH_CLS_BANK","192 个整数常量","无可命名 RAMB 实例；不凭此断言所有 LUT 数量","替换位置 0"],
                ["Feature-map 双 Bank","共享层间激活/Attention 残差来源",f"{by_bram['层间 Feature-map 乒乓缓存']['tiles']:.1f} tiles","与残差专用 FIFO 分开，避免重复计数"],
                ["专用残差 FIFO","i_stream_resi 26 bit；MHA 52/26 bit；MLP 60 bit",f"{by_bram['专用残差缓存']['tiles']:.1f} tiles","主路径与残差旁路时序对齐"]], "表 11　CLS/位置参数及残差相关片上预算")
    note("残差 bypass 保存原整数表示；主路径经 LN、Attention/MLP 与 requantization 后，在对应 merge 处以源码规定的加法/移位/截断语义合并。每层输入 Feature-map 被分叉供主路径与 Attention 残差旁路使用；MLP 旁路保留 Attention 残差加后的整数输入。共享 Feature-map 不能再次全部记成专用残差开销。")
    doc.add_heading("六、功耗与能效：E07 仍需板级采样", 1)
    table(doc, [["指标", "E07 状态", "不能替代的原因"],
                ["18 路 INA226 配置后空闲功耗","待 E07 PWR_RAW/PWR_PHS CSV","不能沿用 E06 的 5.0128 W"],
                ["PS 活跃、PL 不推理功耗","待测","HLS/RTL 不含真实 PS/DDR 电源行为"],
                ["持续推理功耗及配对动态增量","待测","不能沿用 E06 的 8.0556 / 3.0428 W"],
                ["GOP/s/W、mJ/frame、置信区间","待功耗采样后计算","300 MHz 的能量不能按旧功耗简单缩放"],
                ["E07 已有性能工作点",f"{board['fps']:.3f} FPS；{board['effective_gops']:.3f} GOP/s","本次为快速固件，无 INA226 采样"]], "表 12　E07 功耗证据状态")
    note("E07 deploy_power/BOOT.BIN 已提供独立帧率批次及功耗采样功能，预定执行 10 次重复、配置后空闲/PS 活跃无 PL/持续负载各 30 s，采集 18 路 INA226 电源轨。尚未收到本版本 PWR_RAW.CSV、PWR_PHS.CSV、FPS_SUM.CSV，因此正文不宣称 E07 的实测功耗、能效或重复方差。测得后仍只能称受监测电源轨之和，不是墙插总板功耗；软件轮询率也不等同于 INA226 ADC 转换率。")
    doc.add_heading("七、片外流量与 DDR 带宽", 1)
    weight_bytes = int(rtl['aggregate']['axi_requested_bytes']) if rtl else 2_994_624
    traffic = [("输入 MM2S",301056),("Transformer 权重 AXI 请求覆盖",weight_bytes),("输出 S2MM",4000)]
    total = sum(v for _,v in traffic)
    table(doc, [["数据类别", "B/frame", "流量占比", "按 E07 FPS 换算 MB/s", "证据范围"],
                *[[name,f"{value:,}",f"{value/total*100:.3f}%",f"{value*board['fps']/1e6:.3f}",
                   ("E07 RTL ARLEN/ARSIZE 累计 + 板级 FPS 推算" if rtl and "权重" in name else "接口预算；不是板级 APM 计数")] for name,value in traffic],
                ["合计",f"{total:,}","100.000%",f"{total*board['fps']/1e6:.3f}","不是 E07 APM 实测带宽"]], "表 13　E07 每帧流量预算及应用带宽推算")
    note(f"在每帧工作量和接口传输布局保持不变的前提下，每帧流量预算为 {total:,} B，有效计算强度为 {EFFECTIVE_MAC/total:.3f} MAC/B，或 {2*EFFECTIVE_MAC/total:.3f} OP/B。乘本次实测 FPS 得 {total*board['fps']/1e6:.3f} MB/s，属于应用流量率推算，不是新的 APM/DDR 控制器测量；不能把 E06 的 979.335 MB/s 改标签后当成 E07 实测。")
    note("板级权重文件的紧凑 payload 是 231,008 B/层，即 2,772,096 B/帧。AXI 请求覆盖字节按每次接受的 AR 请求累加 (ARLEN+1)×2^ARSIZE；若含重复或宽度/对齐相关读取，则与文件 payload 不相等，不能把两者混为模型参数容量。应用预算也不包含所有 PS cache、指令或系统后台 DDR 流量。")
    if rtl:
        note(f"本次 E07 RTL 的 gmem_w 观察到 {int(rtl['aggregate']['axi_ar_requests']):,} 次 AR 请求、{weight_bytes:,} B 请求覆盖及 {int(rtl['aggregate']['axi_r_beats']):,} 个接受的 R beat。此处为仿真内存模型下的访问计数，不是板级请求延迟、DDR beat-active 时间或带宽饱和度。")
    note("E07 快速/功耗上板镜像未包含 E06 测量镜像的 APM 计数结果。真实 DDR 请求数、beat-active 周期、read/write latency 与 DMA/PL 区间重叠率需本版本板级仪器计数。RTL 回放仅可证明指定 AXI 内存模型下的访问和调度，不能替代真实 DDR 活跃时间。")
    doc.add_heading("八、E06→E07 对比及证据边界", 1)
    table(doc, [["指标", "E06（冻结参考）", "E07", "说明"],
                ["PL 配置频率","249.975021 MHz",f"{evidence['pl_mhz']:.6f} MHz","紧时钟 HLS 调度、DSP binding 与实现策略"],
                ["LUT / FF","213,977 / 142,803","218,759 / 188,403","+4,782 LUT / +45,600 FF"],
                ["DSP / BRAM36","727 / 507.5","736 / 505.0","+9 DSP / −2.5 tiles；不等同于 PE 扩张"],
                ["板级平均帧时间","3.369307 ms",f"{board['ns_per_frame']/1e6:.6f} ms",f"下降 {(1-board['ns_per_frame']/3_369_307)*100:.2f}%"],
                ["串行 FPS","296.796931",f"{board['fps']:.6f}",f"提升 {(board['fps']/296.796931-1)*100:.2f}%；重复协议不同"],
                ["RTL 完整帧 cycles","833,045",f"{rtl['frame_latency_cycles']:,}" if rtl else "单帧回放进行中","HLS 调度变化，不能沿用"],
                ["RTL 帧平均/静态上界","44.110%",f"{rtl['average_to_static_ceiling_percent']:.3f}%" if rtl else "待 RTL 对账","提高时钟不等于提高 MAC/cycle 效率"],
                ["功耗/实测 DDR 带宽","E06 数据已保存","E07 待板级采样","不混合版本"]], "表 14　版本比较（E06 数据仅在此明确标记为参考）")
    if rtl:
        note(f"E07 相对 E06 的完整帧 RTL 周期变化为 {(rtl['frame_latency_cycles']/833045-1)*100:+.3f}%，帧平均/静态上界变化为 {rtl['average_to_static_ceiling_percent']-(EFFECTIVE_MAC/833045/3392*100):+.3f} 个百分点。E07 的时序优化没有增加 PE，而是以更深的局部流水换取 300 MHz 工作点；因此周期效率未必同步提高。应将 LayerNorm 重叠带来的周期改善与 E07 时钟提升带来的每秒速率改善分开解释，不能把 FPS 提升全部归因于 MAC 利用率提高。")
    doc.add_heading("九、来源与补充数据索引", 1)
    note("E07 源码：E04_weight_schedule/E07_timing_300mhz/src/；生成 RTL：hls/work/hls/syn/verilog/；HLS 报告：hls/work/hls/syn/report/；最终 routed 报告：results/candidate05/board_release/{utilization,timing,clock}.rpt/txt。")
    note("本修订的可复核数据：results/paper_evidence/evidence.json、E07_HLS_Operator_Metrics.csv、E07_BRAM_Classified.csv、E07_BRAM_Cells.csv、E07_DSP_Cells.csv、board_uart_100frames.txt。板级 UART 文本来自用户本轮对话，未宣称串口由本机直接采集。")
    result_label = str(Path(rtl['_result_dir']).relative_to(ROOT)) if rtl else "results/paper_rtl_20261003_singleframe_fixed"
    note(f"E07 独立只读 RTL 实验：{result_label}/。identity.json 固定源文件、RTL、输入及观察器身份；只有 accepted_rtl.json 的版本/完成/数值与 sideband 对账通过后，才允许加入完整周期、层窗口、观测峰值和 RTL 效率结论。")
    if rtl:
        note("该实验的 replay_identity.json 和 single_frame_delta.patch 另行记录原生 SystemVerilog 激励端、Verilog testbench、只读输出握手观察器的版本。先前未完整落盘输出的尝试保留为未验收记录，不混入主表。")
        note("日志保留一条原生 UVM_ERROR 标记的未用输入数组警告：C 激励文件仍含原三帧，而 SystemVerilog 控制仅执行一帧；后两帧参考数据未使用。首帧原生输出文件和独立的 1,000 次输出握手均与 C transaction 0 的 data/keep/strb/last 完全匹配。此处报告逐位及 MAC 对账通过，不宣称日志零警告；native_log_qualification.json 保留警告原文及归因。逐层 AXI 活动未采集，CSV 写为 NOT_COLLECTED，不把默认零当作测量结果。")
    if not rtl:
        note("修订状态：已有 E07 板级快速计时、HLS 算子估计和最终实现资源；完整 RTL 回放进行中。本文件不是“所有 E07 实验已经完成”的声明。")
    doc.core_properties.title = "FF-ViT E07 300-MHz 证据分级论文修订"
    doc.core_properties.subject = "Preserve E06; separate E07 board, post-route, HLS and RTL evidence"
    doc.save(output)
    if sha(source) != source_digest:
        raise RuntimeError("source document changed")
    with ZipFile(output) as z:
        if z.testzip() is not None:
            raise RuntimeError("invalid DOCX ZIP")
        ET.fromstring(z.read("word/document.xml"))
    return {"source": str(source), "source_sha256":source_digest,"output":str(output),"output_sha256":sha(output),
            "rtl_included":bool(rtl),"editable_tables":len(doc.tables),"preserved_accuracy_section":True}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, default=WORKSPACE / "论文修改 (1)_E07.docx")
    p.add_argument("--rtl", type=Path)
    args = p.parse_args()
    source = WORKSPACE / "论文修改 (1).docx"
    require_new_output(source,args.output)
    source_tables = extract_source_tables(source)
    hls = hls_metrics(); bram = bram_metrics()
    board = board_metrics(99_990_005,28_678_760,100)
    rpt = ROOT / "results/candidate05/board_release"
    native = (rpt / "utilization.rpt").read_text()
    for name, value in [("CLB LUTs",218759),("CLB Registers",188403),("DSPs",736),("Block RAM Tile",505)]:
        match = re.search(rf"\|\s*{re.escape(name)}\s*\|\s*(\d+)\s*\|",native)
        if not match or int(match[1]) != value:
            raise ValueError(f"resource mismatch: {name}")
    clock = dict(line.split("=",1) for line in (rpt / "clock.txt").read_text().splitlines() if "=" in line)
    evidence = {"version":"E07","board":board,"pl_mhz":float(clock["PL_ACTUAL_MHZ"]),"hls":hls,"bram":bram,
                "board_protocol":{"serial":True,"warmup_frames":2,"timed_batches":1,"timed_frames":100,"logit_check":"after_warmup_only"},
                "source_E06_table_count":len(source_tables),"source_sha256":sha(source),
                "reports_sha256":{name:sha(rpt/name) for name in ["clock.txt","timing.rpt","utilization.rpt"]},
                "E07_top_RTL_sha256":sha(ROOT / "hls/work/hls/syn/verilog/vit_block_top.v"),
                "E07_block0_sha256":sha(ROOT / "src/block0.cpp")}
    rtl = accept_rtl(json.loads(args.rtl.read_text())) if args.rtl else None
    if rtl:
        rtl['_result_dir'] = str(args.rtl.parent.resolve())
        identity = json.loads((args.rtl.parent / "identity.json").read_text())
        if identity["rtl_sha256"]["vit_block_top.v"] != evidence["E07_top_RTL_sha256"]:
            raise ValueError("E07 RTL identity mismatch")
        qualify_rtl_outputs(args.rtl,rtl)
        refresh_budget_annotations(args.rtl.parent / "E07_Frame_Cycle_Budget.csv",rtl["timeline"])
        module_metrics = rtl_module_metrics(rtl["module_layer_rows"],rtl["frame_latency_cycles"])
        with (EVIDENCE / "E07_RTL_Module_Issue_Efficiency.csv").open("w",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=list(module_metrics[0]))
            writer.writeheader();writer.writerows(module_metrics)
        evidence["rtl"] = rtl
    save_csv("E07_HLS_Operator_Metrics.csv",hls)
    save_csv("E07_BRAM_Category_Totals.csv",bram)
    (EVIDENCE / "evidence.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
    result = create_document(source,args.output,evidence,rtl)
    (EVIDENCE / (args.output.stem+"_verification.json")).write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
