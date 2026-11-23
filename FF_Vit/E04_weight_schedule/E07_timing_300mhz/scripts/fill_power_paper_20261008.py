#!/usr/bin/env python3
"""Analyze user-supplied board CSVs and patch only the requested Word XML.

Hardware files and original CSVs are never changed. The document is backed up
before replacement; all ZIP members other than word/document.xml stay intact.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import csv
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import statistics
from zipfile import ZipFile

from docx import Document
from docx.oxml.ns import qn
from scipy.stats import t

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT.parents[1]
OUT = ROOT / 'results/power_csv_20261008'
TARGET = WORK / '论文修改 (1)_E07_待RTL补测.docx'
BACKUP = WORK / '论文修改 (1)_E07_待RTL补测_补功耗前备份_20261008.docx'
COPY = WORK / '论文修改 (1)_E07_功耗与RTL完整修订_20261008.docx'
PHASES = ('PL_CONFIGURED_IDLE', 'PS_ACTIVE_NO_PL', 'FFVIT_SUSTAINED_LOAD')
MAC = 1_246_416_384


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def stats(values):
    n = len(values)
    if n < 2:
        raise ValueError('At least two repetitions required for Student-t interval')
    mean = statistics.mean(values)
    sd = statistics.stdev(values)
    critical = float(t.ppf(.975, n - 1))
    half = critical * sd / math.sqrt(n)
    return dict(n=n, mean=mean, stddev=sd, t95=critical, ci95_half_width=half,
                ci95_low=mean-half, ci95_high=mean+half,
                minimum=min(values), maximum=max(values))


def analyze():
    paths = {name: WORK/name for name in ('FPS_SUM.CSV', 'PWR_RAW.CSV', 'PWR_PHS.CSV')}
    fps_mod = module('existing_fps', ROOT/'board_300mhz/scripts/summarize_fps.py')
    fps = fps_mod.summarize(paths['FPS_SUM.CSV'])
    fps_rows = rows(paths['FPS_SUM.CSV'])
    hz = fps['timer_hz']
    fps['latency_ms_statistics'] = stats([int(r['ticks'])*1000/int(r['frames'])/hz for r in fps_rows])
    fps['fps_statistics'] = stats([int(r['frames'])*hz/int(r['ticks']) for r in fps_rows])
    fps['effective_GOPS'] = 2*MAC*fps['serial_throughput_fps']/1e9
    fps['effective_GMAC_s'] = MAC*fps['serial_throughput_fps']/1e9
    raw = rows(paths['PWR_RAW.CSV'])
    phases = rows(paths['PWR_PHS.CSV'])
    rail_definitions = rows(ROOT/'board_300mhz/deploy_power/zcu102_ina226_rails.csv')
    definitions = {r['rail']:r for r in rail_definitions}
    if len(definitions) != 18:
        raise ValueError('Unexpected rail configuration')
    grouped = defaultdict(list)
    for row in raw:
        grouped[(int(row['repeat']), row['phase'])].append(row)
    phase_map = {(int(r['repeat']),r['phase']):r for r in phases}
    if len(phase_map) != len(phases) or set(grouped) != set(phase_map):
        raise ValueError('Duplicate or unmatched phase records')
    repeats = sorted({r for r,p in phase_map})
    if repeats != list(range(len(repeats))):
        raise ValueError('Noncontiguous repeat identifiers')
    means = {}
    intervals = defaultdict(list)
    for repeat in repeats:
        if {p for r,p in phase_map if r==repeat} != set(PHASES):
            raise ValueError('Incomplete three-phase repeat')
        for phase in PHASES:
            key = (repeat,phase)
            summary, samples = phase_map[key], grouped[key]
            if int(summary['samples']) != len(samples) or int(summary['mismatches']) != 0:
                raise ValueError('Sample count mismatch or output mismatch')
            if {r['rail'] for r in samples} != set(definitions):
                raise ValueError('Missing/extra rail')
            if phase == PHASES[-1] and int(summary['frames']) != len(samples):
                raise ValueError('Expected one power sample per load frame')
            if phase != PHASES[-1] and int(summary['frames']) != 0:
                raise ValueError('Unexpected inference in idle/PS phase')
            prev = -1
            per_rail = defaultdict(list)
            for index,row in enumerate(samples):
                tick = int(row['phase_ticks'])
                rail = definitions[row['rail']]
                if (int(row['sample_index']) != index or not prev < tick < int(summary['ticks'])
                        or row['rail'] != rail_definitions[index % 18]['rail']
                        or row['domain'] != rail['mux_channel']
                        or row['address'].lower() != rail['address'].lower()
                        or int(row['shunt_uohm']) != int(rail['shunt_uohm'])):
                    raise ValueError('Sample ordering/identity/timestamp failure')
                product = int(row['bus_uV'])*int(row['current_uA'])
                expected = (abs(product)//1_000_000) * (-1 if product < 0 else 1)
                if expected != int(row['power_uW']):
                    raise ValueError('Power units/arithmetic mismatch')
                prev = tick
                per_rail[row['rail']].append(row)
            for rail, values in per_rail.items():
                means[(repeat,phase,rail)] = statistics.mean(int(v['power_uW'])/1e6 for v in values)
                intervals[phase].extend((int(b['phase_ticks'])-int(a['phase_ticks']))/hz
                                        for a,b in zip(values,values[1:]))
    totals = {p:[sum(means[r,p,rail] for rail in definitions) for r in repeats] for p in PHASES}
    load_rows = [phase_map[r,PHASES[-1]] for r in repeats]
    frames = sum(int(r['frames']) for r in load_rows)
    ticks = sum(int(r['ticks']) for r in load_rows)
    load_fps = frames*hz/ticks
    load_power = statistics.mean(totals[PHASES[-1]])
    delta_idle = [a-b for a,b in zip(totals[PHASES[-1]], totals[PHASES[0]])]
    delta_ps = [a-b for a,b in zip(totals[PHASES[-1]], totals[PHASES[1]])]
    repeat_stats = []
    for i,repeat in enumerate(repeats):
        record = load_rows[i]
        seconds = int(record['ticks'])/hz
        rate = int(record['frames'])/seconds
        p = totals[PHASES[-1]][i]
        repeat_stats.append(dict(repeat=repeat, idle_W=totals[PHASES[0]][i],
                                 ps_active_no_pl_W=totals[PHASES[1]][i], load_W=p,
                                 load_minus_idle_W=delta_idle[i], frames=int(record['frames']),
                                 load_seconds=seconds, load_FPS=rate,
                                 load_GOPS=2*MAC*rate/1e9,
                                 load_energy_mJ_per_frame=p/rate*1000,
                                 load_GOPS_per_W=2*MAC*rate/1e9/p))
    rails = []
    for rail,definition in definitions.items():
        r = dict(rail=rail, polling_group=definition['mux_channel'])
        for p,label in zip(PHASES,('idle_W','ps_active_no_pl_W','load_W')):
            r[label] = statistics.mean(means[repeat,p,rail] for repeat in repeats)
        r['load_minus_idle_W'] = r['load_W']-r['idle_W']
        r['load_share_percent'] = r['load_W']/load_power*100
        rails.append(r)
    result = dict(version='E07', version_provenance='User assigns these root CSVs to E07; CSVs contain no firmware/bitstream hash or PL-clock field.',
                  timer_hz=hz, effective_MAC_per_frame=MAC,
                  source_files={k:dict(path=str(v),sha256=sha(v),bytes=v.stat().st_size) for k,v in paths.items()},
                  raw_samples=len(raw), phase_records=len(phases), available_power_repetitions=len(repeats),
                  firmware_planned_power_repetitions=10, available_repeats=repeats,
                  power_protocol_status='5 complete repeats available; not the full planned 10-repeat protocol',
                  power_scope='Sum of 18 ZCU102 INA226 monitored rails; NOT wall power or isolated PL dynamic power',
                  fps=fps, phase_power_W={p:stats(totals[p]) for p in PHASES},
                  load_minus_idle_W=stats(delta_idle),load_minus_ps_active_W=stats(delta_ps),
                  power_load=dict(frames=frames,ticks=ticks,total_seconds=ticks/hz,FPS=load_fps,
                                  average_ms_per_frame=1000/load_fps,effective_GOPS=2*MAC*load_fps/1e9,
                                  monitored_load_energy_mJ_per_frame=load_power/load_fps*1000,
                                  monitored_load_GOPS_per_W=2*MAC*load_fps/1e9/load_power,
                                  incremental_energy_mJ_per_frame=statistics.mean(delta_idle)/load_fps*1000),
                  energy_mJ_per_frame_statistics=stats([r['load_energy_mJ_per_frame'] for r in repeat_stats]),
                  GOPS_per_W_statistics=stats([r['load_GOPS_per_W'] for r in repeat_stats]),
                  per_repeat=repeat_stats, per_rail=rails,
                  sampling={p:dict(mean_same_rail_interval_ms=statistics.mean(v)*1000,
                                   min_interval_ms=min(v)*1000,max_interval_ms=max(v)*1000,
                                   effective_same_rail_polling_Hz=1/statistics.mean(v)) for p,v in intervals.items()},
                  negative_samples=dict(count=sum(int(r['power_uW'])<0 for r in raw),
                                        rails=sorted({r['rail'] for r in raw if int(r['power_uW'])<0}),
                                        treatment='Signed readings retained; near-zero rail offset not clipped'),
                  limitations=['95% Student-t intervals describe repeat-to-repeat variation, not sensor calibration accuracy.',
                               'Repetitions are sequential; thermal drift and autocorrelation are not removed.',
                               'No per-frame latency distribution; FPS variability is across 100-frame batch means.',
                               'Power-window FPS includes per-frame INA226 polling; dedicated FPS excludes it.',
                               '18 rails are polled sequentially; this is not a simultaneous instantaneous sum.',
                               'No new E07 APM/DDR measurement, network/cloud timing, or dataset accuracy evidence.'])
    return result


def write_csv(path, records):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w = csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)


def para(doc, prefix):
    found = [p for p in doc.paragraphs if p.text.startswith(prefix)]
    if len(found)!=1:raise ValueError(f'Paragraph match {prefix}: {len(found)}')
    return found[0]


def get_table(doc, first_cell):
    found = [x for x in doc.tables if x.cell(0,0).text==first_cell]
    if len(found)!=1:raise ValueError(f'Table match {first_cell}: {len(found)}')
    return found[0]


def replace_block(doc, reference, start, stop):
    a,b = para(doc,start)._p,para(doc,stop)._p
    ra,rb = para(reference,start)._p,para(reference,stop)._p
    parent=a.getparent();index=parent.index(a)
    cur=a
    while cur is not b:
        nxt=cur.getnext();parent.remove(cur);cur=nxt
    cur=ra
    while cur is not rb:
        parent.insert(index,deepcopy(cur));index+=1;cur=cur.getnext()


def set_text(p, text):
    props=deepcopy(p._p.pPr) if p._p.pPr is not None else None
    p.text=text
    if props is not None:
        old=p._p.pPr
        if old is not None:p._p.remove(old)
        p._p.insert(0,props)


def fill_document(data):
    if BACKUP.exists() or COPY.exists():raise FileExistsError('Refusing to overwrite prior backup/result')
    source_hash=sha(TARGET)
    helper=module('word_helpers',ROOT/'scripts/update_paper_e07.py')
    accepted=json.loads((ROOT/'results/paper_rtl_20261003_singleframe_fixed/accepted_rtl.json').read_text())
    helper.accept_rtl(accepted)
    reference=Document(WORK/'论文修改 (1)_E07.docx')
    doc=Document(TARGET)
    # Bring in already accepted RTL tables; never rerun HLS/RTL/Vivado here.
    replace_block(doc,reference,'表 6　','四、')
    replace_block(doc,reference,'四、','五、')
    f=data['fps'];rate=f['serial_throughput_fps'];power=data['power_load']
    boardratio=MAC*rate/(300.21509875*1e6*3392)*100
    efficiency=next(x for x in doc.tables if x.cell(1,0).text=='单帧 effective / issued MAC')
    for row in efficiency.rows:
        if row.cells[0].text=='板级端到端速率/静态上界':row.cells[1].text=f'{boardratio:.3f}%'
    set_text(para(doc,'证据标签：'),'证据标签：BOARD_MEASURED 为用户提供的板级 UART/原始 CSV；POST_ROUTE 为最终实现网表/时序报告；HLS_ESTIMATE 为 HLS 综合报告；RTL_OBSERVATION 为独立只读 RTL 回放；DERIVED 为按明确公式换算。2026-10-08 CSV 由用户指定为 E07 测量，CSV 未内嵌固件/bitstream 哈希及 PL 时钟字段；配套部署身份另存，不能仅凭 CSV 自证启动镜像。')
    set_text(para(doc,'表 7'),'表 7　E07 独立串行帧率批次测量（FPS_SUM.CSV）')
    old=next(x for x in doc.tables if x.cell(1,0).text=='计时器频率')
    results=[['指标','E07 结果','测量范围'],
             ['计时器频率',f"{data['timer_hz']:,} Hz",'PS timer，非 PL cycle counter'],
             ['正式计时帧数',f"{f['frames']:,}",'10 批 × 100 帧；2 帧预热不计入'],
             ['原始 timer delta 总和',f"{round(f['total_seconds']*data['timer_hz']):,} ticks",'按 10 批原始 ticks 求和'],
             ['全部批次计时总和',f"{f['total_seconds']*1000:.6f} ms",'不含批次间校验和 CSV/UART 写入'],
             ['平均单帧时间',f"{f['mean_repeat_average_latency_ms']:.6f} ms",'串行完整帧；不是跨帧流水'],
             ['串行帧率',f'{rate:.6f} FPS','总完成帧数 ÷ 全部批次计时总和'],
             ['有效吞吐量',f"{f['effective_GMAC_s']:.6f} GMAC/s",'每帧有效工作量 1,246,416,384 MAC'],
             ['2 operations/MAC',f"{f['effective_GOPS']:.6f} GOP/s",'不是静态峰值吞吐量'],
             ['输出一致性','10 批末帧均 mismatches=0','每批末帧检查 1,000 logits；不声称每帧均核查'],
             ['批次平均延迟标准差',f"{f['stddev_repeat_average_latency_ms']*1000:.6f} μs",'n=10 批均值；不是逐帧标准差'],
             ['批次平均延迟 95% CI',f"±{f['latency_ms_statistics']['ci95_half_width']*1000:.6f} μs",'Student-t，df=9；仅重复统计区间'],
             ['批次 FPS 标准差',f"{f['stddev_repeat_fps']:.6f} FPS",'n=10 批均值'],
             ['跨帧重叠','无','同一固定输入重复推理；非验证集精度测试']]
    new=helper.table(doc,results);old._tbl.addprevious(new._tbl);old._tbl.getparent().remove(old._tbl)
    set_text(para(doc,'计时包括逐帧'),'计时包括逐帧 cache 操作、PS 调度、输入 DDR→DMA→PL、完整推理、输出 PL→DMA→DDR 及完成轮询；不包含初始 SD 文件读取、一次性输入打包、两帧预热，以及计时窗口外的 UART/CSV 写入、INA226 采样和批次结果校验。该结果为固定输入的 10 批串行执行速率，不是跨帧流水或包含文件读取、解码、网络上传的端到端速度。标准差与置信区间针对 100 帧批次均值，不能当作逐图像延迟分布。原先 UART 的 100 帧结果 348.655259 FPS 作为历史记录保留，本文主结果更新为当前 1,000 帧 CSV 的 348.677480 FPS。')
    set_text(para(doc,'六、'),'六、E07 板级功耗、能效与重复统计')
    set_text(para(doc,'表 12'),'表 12　E07 受监测电源轨功耗及配套能效')
    old=next(x for x in doc.tables if x.cell(0,1).text=='E07 状态')
    phase=data['phase_power_W']
    stat=lambda p:f"{phase[p]['mean']:.6f} ± {phase[p]['ci95_half_width']:.6f} W"
    results=[['指标','E07 结果','定义及证据范围'],
             ['实际功耗重复数 / 原始样本','5 轮 / 112,305 条','每轮三阶段各约 30 s；不是预定的 10 轮'],
             ['配置后空闲功耗',stat(PHASES[0]),'18 路均值之和；PL 已配置且时钟保留'],
             ['PS 活跃、PL 不推理功耗',stat(PHASES[1]),'PS 执行固定输入遍历；不启动推理'],
             ['持续推理负载功耗',stat(PHASES[2]),'18 路受监测电源轨；不是墙插功耗'],
             ['负载 − 配置后空闲',f"{data['load_minus_idle_W']['mean']:.6f} ± {data['load_minus_idle_W']['ci95_half_width']:.6f} W",'同轮配对差；不是纯 PL 动态功耗'],
             ['负载 − PS 活跃无 PL',f"{data['load_minus_ps_active_W']['mean']:.6f} ± {data['load_minus_ps_active_W']['ci95_half_width']:.6f} W",'同轮配对差；仅作替代参考基线'],
             ['配套功耗负载帧数 / 时间',f"{power['frames']:,} / {power['total_seconds']:.6f} s",'5 个负载阶段；每阶段 10,461 帧'],
             ['配套功耗负载 FPS',f"{power['FPS']:.6f}",'含每帧 INA226 轮询，单独于纯帧率报告'],
             ['配套功耗负载吞吐',f"{power['effective_GOPS']:.6f} GOP/s",'每 MAC 两个操作'],
             ['受监测负载能量/帧',f"{power['monitored_load_energy_mJ_per_frame']:.6f} mJ/frame",'负载功耗 ÷ 配套负载 FPS'],
             ['受监测负载能效',f"{power['monitored_load_GOPS_per_W']:.6f} GOP/s/W",'配套负载吞吐 ÷ 负载功耗'],
             ['配对增量能量/帧',f"{power['incremental_energy_mJ_per_frame']:.6f} mJ/frame",'负载−空闲增量 ÷ 配套 FPS；不是总能量']]
    new=helper.table(doc,results);old._tbl.addprevious(new._tbl);old._tbl.getparent().remove(old._tbl)
    set_text(para(doc,'E07 deploy_power/BOOT.BIN'),'本次分析使用用户提供的根目录 FPS_SUM.CSV、PWR_RAW.CSV 和 PWR_PHS.CSV。功耗 CSV 实际包含 repeat=0–4 的 5 轮完整测量，各轮配置后空闲、PS 活跃但 PL 不推理、持续推理负载各约 30 s，每阶段均覆盖相同的 18 路电源轨；112,305 条原始记录与 15 条阶段摘要逐项对账。不能将可用 5 轮写成固件预定的 10 轮已完成。先对每轮每轨求均值，再求 18 路均值之和，最后跨轮统计；表中 ± 为 95% Student-t 置信区间，n=5、df=4、临界值 2.776445，不是传感器标定误差。')
    anchor=para(doc,'七、')._p
    def insert_note(text):
        p=doc.add_paragraph(text);anchor.addprevious(p._p)
    insert_note(f"纯帧率 10 批共 1,000 帧，得到 {rate:.6f} FPS、{f['mean_repeat_average_latency_ms']:.6f} ms/frame 和 {f['effective_GOPS']:.6f} GOP/s。功耗阶段共完成 {power['frames']:,} 帧，配套速率为 {power['FPS']:.6f} FPS；负载功耗 {phase[PHASES[2]]['mean']:.6f} W 对应 {power['monitored_load_energy_mJ_per_frame']:.6f} mJ/frame 与 {power['monitored_load_GOPS_per_W']:.6f} GOP/s/W。能效使用同一功耗负载窗口的帧率，不将纯帧率与另一个功耗窗口混合。功耗摘要中的 5 个负载阶段与帧率 CSV 的 10 个批次，末帧输出检查均为零差异；不是所有运行帧逐帧比较。")
    insert_note('测量范围限定为 18 路 INA226 受监测电源轨之和，不包含墙插交流输入、未监测供电路径或电源转换损耗。轮询分组 PS/PL 还覆盖 DDR、I/O 和收发器供电，不能直接解释为纯 PS/PL 逻辑功耗。VADJ_FMC 的负载均值约 −0.459 mW，为近零轨道的微小负偏移；本次保留带符号原始读数、不裁零、不据此解释为负耗能。PS 活跃无 PL 的均值略低于配置后空闲，三阶段顺序、温度及读数波动不同，不能推断 PS 活跃导致负功耗。')
    insert_note('各重复按固定顺序执行，负载功耗由首轮约 9.456 W 逐步上升至末轮约 9.535 W；置信区间只描述这 5 轮的重复波动，不消除热漂移、时间相关性或 INA226/分流电阻的系统误差。当前 CSV 不内嵌 BOOT.BIN/bitstream 哈希，版本由用户指定为 E07；建议随论文证据保存本次启动 UART 和所用镜像 manifest。')
    sampling=data['sampling']
    insert_note(f"18 路按顺序轮询而非同步采样。配置后空闲和 PS 活跃阶段，每轨平均采样间隔分别为 {sampling[PHASES[0]]['mean_same_rail_interval_ms']:.3f}、{sampling[PHASES[1]]['mean_same_rail_interval_ms']:.3f} ms（约 11.111 Hz/轨）；负载阶段每帧采一轨，每轨平均 {sampling[PHASES[2]]['mean_same_rail_interval_ms']:.3f} ms（约 {sampling[PHASES[2]]['effective_same_rail_polling_Hz']:.3f} Hz/轨）。这些是软件读出/轮询率，不是 INA226 内部 ADC 转换频率，也不能将非同步的轨道记录相加声称瞬时整板峰值功耗。")
    caption=doc.add_paragraph('表 12a　五轮功耗及配套负载速率',style='Caption');anchor.addprevious(caption._p)
    tab=helper.table(doc,[['轮次','空闲/W','PS活跃无PL/W','负载/W','负载 FPS']]+[[r['repeat'],f"{r['idle_W']:.6f}",f"{r['ps_active_no_pl_W']:.6f}",f"{r['load_W']:.6f}",f"{r['load_FPS']:.6f}"] for r in data['per_repeat']]);anchor.addprevious(tab._tbl)
    caption=doc.add_paragraph('表 12b　18 路电源轨平均功耗分配（单位 mW）',style='Caption');anchor.addprevious(caption._p)
    rail_rows=[['电源轨','轮询分组','配置后空闲','PS活跃无PL','推理负载','负载−空闲']]
    rail_rows += [[r['rail'],r['polling_group'],*[f"{r[k]*1000:.3f}" for k in ('idle_W','ps_active_no_pl_W','load_W','load_minus_idle_W')]] for r in data['per_rail']]
    rail_rows.append(['18 路合计','—',f"{phase[PHASES[0]]['mean']*1000:.3f}",f"{phase[PHASES[1]]['mean']*1000:.3f}",f"{phase[PHASES[2]]['mean']*1000:.3f}",f"{data['load_minus_idle_W']['mean']*1000:.3f}"])
    tab=helper.table(doc,rail_rows);anchor.addprevious(tab._tbl)
    traffic=next(x for x in doc.tables if x.cell(0,0).text=='数据类别')
    for row in traffic.rows[1:]:row.cells[3].text=f"{int(row.cells[1].text.replace(',',''))*rate/1e6:.3f}"
    set_text(para(doc,'在每帧工作量'),'在每帧工作量和接口传输布局保持不变的前提下，每帧流量预算为 3,299,680 B，有效计算强度为 377.739 MAC/B，或 755.477 OP/B。乘最新 1,000 帧纯帧率 CSV 得 '+f'{3299680*rate/1e6:.3f}'+' MB/s，属于应用流量率推算，不是新的 APM/DDR 控制器测量；不能把 E06 的 979.335 MB/s 改标签后当成 E07 实测。')
    compare=next(x for x in doc.tables if x.cell(0,1).text=='E06（冻结参考）')
    e06=json.loads((WORK/'E04_weight_schedule/E06_measurement/results/E06_Board_Throughput_DDR_Summary.json').read_text())
    for row in compare.rows[1:]:
        label=row.cells[0].text
        if label=='板级平均帧时间':
            row.cells[2].text=f"{f['mean_repeat_average_latency_ms']:.6f} ms";row.cells[3].text=f"下降 {(1-f['mean_repeat_average_latency_ms']/e06['mean_ms_per_frame'])*100:.2f}%；本次 10×100 帧"
        elif label=='串行 FPS':
            row.cells[2].text=f'{rate:.6f}';row.cells[3].text=f"提升 {(rate/e06['sustained_fps']-1)*100:.2f}%；两版均 10×100 帧串行协议"
        elif label=='RTL 完整帧 cycles':row.cells[2].text=f"{accepted['frame_latency_cycles']:,}";row.cells[3].text='独立单帧 RTL；比 E06 增加 16,982 cycles'
        elif label=='RTL 帧平均/静态上界':row.cells[2].text=f"{accepted['average_to_static_ceiling_percent']:.3f}%";row.cells[3].text='每帧有效 MAC 不变；不是板级端到端利用率'
        elif label=='功耗/实测 DDR 带宽':
            row.cells[2].text=f"功耗 {phase[PHASES[2]]['mean']:.6f} W；DDR 待测";row.cells[3].text='E07 功耗 n=5 已采；不沿用 E06 DDR'
    set_text(para(doc,'本修订的可复核数据：'),'本修订的可复核数据：results/paper_evidence/evidence.json、E07_HLS_Operator_Metrics.csv、E07_BRAM_Classified.csv、E07_BRAM_Cells.csv、E07_DSP_Cells.csv；根目录 FPS_SUM.CSV/PWR_RAW.CSV/PWR_PHS.CSV 原始数据及 SHA-256 汇总位于 results/power_csv_20261008。历史 board_uart_100frames.txt 保留但不再作为最新吞吐主值。全部板级记录由用户提供，不宣称串口或 SD 由本机直接采集。')
    set_text(para(doc,'E07 独立只读 RTL 实验：'),'E07 已接受的独立只读 RTL 实验：results/paper_rtl_20261003_singleframe_fixed/accepted_rtl.json。完整帧 850,027 cycles，effective/issued MAC 对账通过，1000 个输出及 AXI-Stream sideband 检查通过；保留原始日志中仅与三帧参考向量未全部消费有关的已限定警告，不能声称日志完全无警告。该 RTL 结果不是板级测量，单帧不能测跨帧 RTL 启动间隔。')
    set_text(para(doc,'修订状态：'),'修订状态：E07 最终实现资源/时序、单帧 RTL 周期/MAC 对账、最新 10×100 帧串行性能、可用 5 轮三阶段电源轨功耗已补齐。E07 实测 APM/DDR 活跃带宽、云端/网络端到端时延、传感器系统标定，以及固件原计划的后 5 轮功耗记录仍未提供，不宣称所有实验已完成。原文件名中的“待RTL补测”仅为保留用户指定路径。')
    # Repackage only document.xml to keep every original image/OLE/style part byte-identical.
    shutil.copy2(TARGET,BACKUP)
    with ZipFile(TARGET) as z, ZipFile(COPY,'w') as out:
        for info in z.infolist():
            out.writestr(info,doc._element.xml.encode('utf-8') if info.filename=='word/document.xml' else z.read(info.filename))
    if sha(TARGET)!=source_hash:raise ValueError('Source changed during update; replacement aborted')
    # Atomic same-directory replacement; pre-update original is retained in BACKUP.
    temp=TARGET.with_name(TARGET.name+'.power_update.tmp')
    shutil.copy2(COPY,temp);os.replace(temp,TARGET)
    return dict(target=str(TARGET),copy=str(COPY),backup=str(BACKUP),before_sha256=source_hash,
                after_sha256=sha(TARGET),backup_sha256=sha(BACKUP),only_changed_zip_member='word/document.xml')


def main():
    data=analyze()
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'E07_Power_FPS_Summary.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    write_csv(OUT/'E07_Power_Per_Repeat.csv',data['per_repeat'])
    write_csv(OUT/'E07_Power_Per_Rail.csv',data['per_rail'])
    summary=[]
    for phase,s in data['phase_power_W'].items():summary.append(dict(metric=phase,value=s['mean'],unit='W',n=s['n'],ci95_half_width=s['ci95_half_width']))
    for metric,value,unit,n in [('dedicated_FPS',data['fps']['serial_throughput_fps'],'FPS',10),('dedicated_latency_ms',data['fps']['mean_repeat_average_latency_ms'],'ms',10),('power_window_FPS',data['power_load']['FPS'],'FPS',5),('power_window_GOPS_per_W',data['power_load']['monitored_load_GOPS_per_W'],'GOPS/W',5),('power_window_energy_mJ_per_frame',data['power_load']['monitored_load_energy_mJ_per_frame'],'mJ/frame',5)]:
        summary.append(dict(metric=metric,value=value,unit=unit,n=n,ci95_half_width='see_JSON'))
    write_csv(OUT/'E07_Power_FPS_Table.csv',summary)
    audit=fill_document(data)
    (OUT/'document_update_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(document=audit,raw_samples=data['raw_samples'],power_repeats=data['available_power_repetitions'],FPS=data['fps']['serial_throughput_fps'],load_W=data['phase_power_W'][PHASES[-1]]['mean'],GOPS_per_W=data['power_load']['monitored_load_GOPS_per_W']),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
