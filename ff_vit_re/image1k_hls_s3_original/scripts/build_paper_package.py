#!/usr/bin/env python3
"""Publish evidence-labelled stage tables and copy corrected sensitivity data."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.hls_csim import sha256
from src.paper_package import formal_stage,completeness,hls_success,validate_sensitivity


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--require-complete',action='store_true')
    args=parser.parse_args()
    paper=ROOT/'paper';paper.mkdir(exist_ok=True)
    sources={};rows=[]
    def read(path):
        path=Path(path);sources[str(path)]=sha256(path)
        return json.loads(path.read_text())
    historical=ROOT.parent/'image_lianghu/reports'
    for name,file in [('FP32 197-token','fp32_197_val50k_official_crop09.json'),
                      ('FP32 HLS-196','fp32_hls196_val50k_official_crop09.json'),
                      ('W3 PTQ HLS-196','w3_ptq_val50k_official_crop09.json')]:
        p=historical/file;r=read(p)
        row=formal_stage(name,{'sample_count':r['sample_count'],'top1':r['top1_percent']/100,
                              'top5':r['top5_percent']/100},'historical_software_50k')
        row.update(source=str(p),checkpoint_sha256=r['checkpoint_sha256']);rows.append(row)
    sensitivity=ROOT/'reports/sensitivity_v2'
    sensitivity_version=2 if (sensitivity/'operator_sensitivity.json').exists() else 1
    if sensitivity_version==1:sensitivity=ROOT/'reports'
    operator=read(sensitivity/'operator_sensitivity.json')
    baseline=next(r for r in operator['records'] if r['experiment_id']=='baseline')
    row=formal_stage('W3 QAT HLS-196',baseline,'software_surrogate_50k')
    row.update(source=str(sensitivity/'operator_sensitivity.json'),checkpoint_sha256=baseline['checkpoint_sha256']);rows.append(row)
    for name,file in [('MLP LN2 s3 / GELU u3 QAT','mlp_qat_checkpoint.json'),
                      ('Attention + MLP strict QAT','attention_qat_checkpoint.json')]:
        p=ROOT/'metadata'/file;r=read(p)['best_formal']
        row=formal_stage(name,r,'software_surrogate_50k_model_selection')
        row.update(source=str(p),checkpoint_sha256=r['checkpoint_sha256']);rows.append(row)
    exact_path=ROOT/'reports/exact_50k.json';exact_formal=False
    if exact_path.exists():
        r=read(exact_path);row=formal_stage('Original HLS integer deployment',r,'exact_integer_50k')
        if r.get('stage')!='exact_integer_50k':raise ValueError('incorrect exact formal stage')
        row.update(source=str(exact_path),checkpoint_sha256=rows[-1]['checkpoint_sha256']);rows.append(row)
        exact_formal=True
    hls_path=ROOT/'reports/hls_csim.json';hls=read(hls_path) if hls_path.exists() else {}
    counts={}
    for family in ('operator','layer','cumulative'):
        path=sensitivity/f'{family}_sensitivity.json';r=read(path)
        validate_sensitivity(r,{'operator':17,'layer':36,'cumulative':24}[family])
        counts[family]=len(r['records'])
        for suffix in ('json','csv','md'):
            source=sensitivity/f'{family}_sensitivity.{suffix}'
            if source.exists():shutil.copy2(source,paper/source.name)
    state=completeness(dict(**counts,sensitivity_version=sensitivity_version,exact50k=exact_formal,
                            hls_passed=hls_success(hls),hls_sample_count=len(hls.get('samples',[]))))
    state.update(sensitivity_version=sensitivity_version,inputs_sha256=sources,
                 target_69_reached=bool(exact_formal and hls_success(hls) and rows[-1]['top1_percent']>=69),
                 hls_sample_count=len(hls.get('samples',[])),hls_passed=hls_success(hls))
    (paper/'completeness.json').write_text(json.dumps(state,sort_keys=True,indent=2)+'\n')
    with (paper/'stage_accuracy.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    (paper/'stage_accuracy.json').write_text(json.dumps(rows,sort_keys=True,indent=2)+'\n')
    lines=['# ImageNet-1K 原始 HLS 位宽实验数据','',
           '| 阶段 | Top-1 (%) | Top-5 (%) | 样本数 | 评价类型 |',
           '|---|---:|---:|---:|---|']
    lines += [f"| {r['stage']} | {r['top1_percent']:.3f} | {r['top5_percent']:.3f} | {r['sample_count']} | {r['kind']} |" for r in rows]
    lines += ['',f"HLS 固定样本：{len(hls.get('samples',[]))}；逐位比较状态：{hls.get('status','NOT_RUN')}。",
              f"数据完整性：{'完整' if state['complete'] else '尚缺 '+', '.join(state['missing'])}。",
              '', '所有软件正式结果采用 resize 248 / center crop 224 / bicubic / ImageNet mean/std。',
              'FP32 与 W3 PTQ 复用已归档的同协议 50k 报告，来源及 SHA-256 见 completeness.json。',
              '69% 是目标；surrogate QAT 精度不等于整数部署精度，HLS 少量样本也不是 50k 准确率。',
              'MLP/Attention 使用完整 50k 验证精度选择 epoch，因此该验证集不是选模后的独立无偏测试集。',
              '敏感度正式论文数据应使用 v2：修正 Attention residual 必须同时进入 LN2 与 MLP skip 的语义。',
              '现有 QAT 的渐进层次顺序来源于 v1 排名；修正后的 v2 结果另行保存，不能宣称训练使用 v2 排名。','']
    text='\n'.join(lines)
    (ROOT/'reports/stage_accuracy_summary.md').write_text(text)
    (paper/'RESULTS_CN.md').write_text(text)
    print(json.dumps(state,sort_keys=True))
    if args.require_complete and not state['complete']:raise SystemExit(1)


if __name__=='__main__':main()
