"""Validate complete runs, merge element-weighted errors, and write evidence."""
import csv
import json
import math
from pathlib import Path
import u3_validation as u


def aggregate(rows):
    count=sum(int(r["count"]) for r in rows)
    if count<=0:raise ValueError("empty observations")
    def mean(key):return sum(int(r["count"])*float(r[key]) for r in rows)/count
    result=dict(count=count,mae_lsb=mean("mae_lsb"),
        rmse_lsb=math.sqrt(sum(int(r["count"])*float(r["rmse_lsb"])**2 for r in rows)/count),
        max_ae_lsb=max(float(r["max_ae_lsb"]) for r in rows),
        exact_rate=mean("exact_rate"),within_1_lsb_rate=mean("within_1_lsb_rate"))
    if all(r.get("real_mae") not in (None,"NOT_MEASURED","") for r in rows):
        result.update(real_mae=mean("real_mae"),
            real_rmse=math.sqrt(sum(int(r["count"])*float(r["real_rmse"])**2 for r in rows)/count),
            real_max_ae=max(float(r["real_max_ae"]) for r in rows))
    return result


def read_csv(path):
    with path.open(newline="") as stream:return list(csv.DictReader(stream))


def main():
    accuracy=[];units=[];parameters=[];provenance=[]
    expected_count=dict(Softmax=177020928,Softmax_EXP=177020928,
        Softmax_Reciprocal=903168,LayerNorm=115605504,GELU=231211008)
    for name in ("plantvillage","nwpu"):
        out=u.HERE / "outputs" / (name+"_u3")
        manifest=json.loads((out / "manifest.json").read_text())
        if not manifest["preserved_sources"]:raise ValueError("source preservation failed")
        for path,sha in manifest["sources"].items():
            if u.digest(path)!=sha:raise ValueError("source changed since measurement: "+path)
        data=json.loads((out / "dataset_identity.json").read_text())
        cal=json.loads((out / "calibration_report.json").read_text())
        if cal["changes"]["unauthorized_byte_changes"]!=0:raise ValueError("unexpected model changes")
        if data["selected_calibration_test_sha256_overlap"] or data["selected_calibration_val_sha256_overlap"]:
            raise ValueError("held-out calibration overlap")
        if [r["block"] for r in cal["blocks"]]!=list(range(12)):raise ValueError("incomplete calibration")
        original=u.load_native_artifact(u.dataset_spec(name))
        candidate,_=u.exact.load_artifact(out / "u3_artifact")
        for b,(old,new) in enumerate(zip(original["blocks"],candidate["blocks"])):
            if not (old["softmax"]["exp"]==new["softmax"]["exp"]).all():raise ValueError("EXP changed")
            for interval in (slice(0,6),slice(8,11)):
                if not (old["softmax"]["scalars"][interval]==new["softmax"]["scalars"][interval]).all():
                    raise ValueError("EXP/reciprocal addressing changed")
            if int(new["softmax"]["scalars"][13])!=3:raise ValueError("non-U3 block")
            for variant,p in (("U8",old),("U3",new)):
                scalars=list(map(int,p["softmax"]["scalars"]))
                parameters.append(dict(dataset=name,variant=variant,block=b,
                    probability_bits=scalars[13],output_scale=p["softmax"].get("output_scale",1/256),
                    softmax_scalars=json.dumps(scalars),aq_scalars=json.dumps(p["a_lut"]["scalars"].tolist()),
                    exp_entries=32,reciprocal_entries_per_bank=64,reciprocal_storage_bits=8,
                    aq_entries=64,aq_output_bits=3))
        for variant in ("U8","U3"):
            dest=out / variant
            measured=json.loads((dest / "accuracy.json").read_text())
            for split,row in measured.items():
                predictions=read_csv(dest / (split+"_predictions.csv"))
                if not row["complete_split"] or row["sample_count"]!=data[split+"_count"]:
                    raise ValueError("full split not measured")
                if [int(r["index"]) for r in predictions]!=list(range(row["sample_count"])):
                    raise ValueError("missing or duplicate prediction indices")
                if sum(int(r["correct"]) for r in predictions)!=row["correct"]:
                    raise ValueError("accuracy count disagrees with predictions")
                if u.digest(dest / (split+"_predictions.csv"))!=row["predictions_sha256"]:
                    raise ValueError("prediction hash mismatch")
                accuracy.append(dict(dataset=name,variant=variant,split=split,**row))
            rows=read_csv(dest / "unit_accuracy.csv")
            if len(rows)!=72 or any(int(r["input_images"])!=128 for r in rows):
                raise ValueError("incomplete local audit")
            if any(int(r.get("independent_integer_mismatches") or 0) for r in rows):
                raise ValueError("LN independent integer mismatch")
            for operator in expected_count:
                result=aggregate([r for r in rows if r["operator"]==operator])
                if operator=="Softmax":
                    selected=[r for r in rows if r["operator"]==operator]
                    result["reference_clip_count"]=sum(int(r["reference_clip_count"]) for r in selected)
                    result["reference_clip_rate"]=result["reference_clip_count"]/result["count"]
                if result["count"]!=expected_count[operator]:
                    raise ValueError(f"unexpected {operator} count: {result['count']}")
                units.append(dict(dataset=name,variant=variant,operator=operator,
                    scope="SAME_128_TEST_IMAGES_NEW_CAPTURE",**result))
            ex=read_csv(dest / "gelu_exhaustive.csv")
            if len(ex)!=12 or sum(int(r["count"]) for r in ex)!=24576:raise ValueError("GELU exhaustive count")
            units.append(dict(dataset=name,variant=variant,operator="GELU",scope="EXHAUSTIVE_S11_2048",**aggregate(ex)))
        fixture=json.loads((out / "historical_fixture_check.json").read_text())
        for check in fixture.values():
            if check["mismatches"] or check["checked_integer_count"]!=490600:raise ValueError("historical replay failed")
        provenance.append(dict(dataset=name,original_weights_sha256=u.digest(u.dataset_spec(name)["weights"]),
            candidate_weights_sha256=u.digest(out / "weights_u3.bin"),historical_Csim_fixture_integers=490600,
            source_preservation="PASS",training="NOT_EXECUTED",new_HLS_Csim="NOT_MEASURED",
            RTL_cosim="NOT_MEASURED",FPGA="NOT_MEASURED"))
    for row in accuracy:
        baseline=next(r for r in accuracy if r["dataset"]==row["dataset"] and r["split"]==row["split"] and r["variant"]=="U8")
        row["delta_vs_U8_pp"]=row["top1_percent"]-baseline["top1_percent"]
    u.write_csv(u.HERE / "accuracy_comparison.csv",accuracy)
    u.write_csv(u.HERE / "global_unit_accuracy.csv",units)
    u.write_csv(u.HERE / "hls_parameter_contract.csv",parameters)
    u.save_json(u.HERE / "summary.json",dict(accuracy=accuracy,units=units,provenance=provenance,
        checks="PASS: complete unique indices, correct counts, frozen source hashes, allowed byte changes, EXP unchanged, calibration disjoint, same 128 images, element counts"))
    tex=[r"\begin{tabular}{llrrr}",r"\hline",r"Dataset & Split & U8 Top-1 (\%) & U3 Top-1 (\%) & $\Delta$ (pp) \\",r"\hline"]
    for name in ("plantvillage","nwpu"):
        for split in ("val","test"):
            pair={r["variant"]:r for r in accuracy if r["dataset"]==name and r["split"]==split}
            tex.append(f"{name} & {split} & {pair['U8']['top1_percent']:.4f} & {pair['U3']['top1_percent']:.4f} & {pair['U3']['delta_vs_U8_pp']:+.4f} \\\\")
    tex += [r"\hline",r"\end{tabular}","% Full HLS-integer software replay. NOT FPGA board accuracy."]
    (u.HERE / "accuracy_table.tex").write_text("\n".join(tex)+"\n")
    tex=[r"\begin{tabular}{lllrrrrr}",r"\hline",r"Dataset & Domain & Unit & MAE (LSB) & RMSE (LSB) & MaxAE & Exact (\%) & $\leq1$ LSB (\%) \\",r"\hline"]
    for row in units:
        if row["scope"]!="SAME_128_TEST_IMAGES_NEW_CAPTURE" or row["operator"] not in ("Softmax","LayerNorm","GELU"):continue
        tex.append(f"{row['dataset']} & {row['variant']} & {row['operator']} & {row['mae_lsb']:.6f} & {row['rmse_lsb']:.6f} & {row['max_ae_lsb']:g} & {100*row['exact_rate']:.4f} & {100*row['within_1_lsb_rate']:.4f} \\\\")
    tex += [r"\hline",r"\end{tabular}","% Code-domain comparison against quantized float references on identical local inputs."]
    (u.HERE / "lut_accuracy_table.tex").write_text("\n".join(tex)+"\n")
    lines=["Softmax U3 HLS 整数口径复测（2026-10-10）", "",
        "本次完成 PlantVillage / NWPU 的全量验证集和测试集整数软件评价；不训练，不修改原工程，不上板。",
        "改变的是 Softmax 概率输出 U8→U3 及其输出尺度、倒数表、AQ 表重标定，不是全部激活改位宽。",
        "EXP 表与地址、倒数地址、全部权重/偏置、LN、GELU、残差、Patch/Head ROM 均冻结。",
        "这是一套无训练、256 张训练校准样本的 U3 标定结果，不代表重新 QAT 后 U3 能达到的最佳精度。", "",
        "一、全量 Top-1（正确数/总数；CALCULATED from fresh per-image records）"]
    for row in accuracy:
        lines.append(f"{row['dataset']} {row['split']} {row['variant']}: {row['correct']}/{row['sample_count']} = {row['top1_percent']:.6f}%; 对原生 U8 差值 {row['delta_vs_U8_pp']:+.6f} pp")
    lines += ["来源：outputs/{plantvillage,nwpu}_u3/{U8,U3}/accuracy.json 与每个 split_predictions.csv；汇总 accuracy_comparison.csv。", "",
        "二、同一 128 张测试图像上的局部误差（新捕获，不复用旧 LN/GELU 自然分布统计）"]
    for row in units:
        if row["scope"]!="SAME_128_TEST_IMAGES_NEW_CAPTURE" or row["operator"] not in ("Softmax","LayerNorm","GELU"):continue
        lines.append(f"{row['dataset']} {row['variant']} {row['operator']}: MAE={row['mae_lsb']:.6f} LSB, RMSE={row['rmse_lsb']:.6f}, MaxAE={row['max_ae_lsb']:g}, Exact={100*row['exact_rate']:.4f}%, <=1 LSB={100*row['within_1_lsb_rate']:.4f}%")
    lines += ["逐层表：outputs/*_u3/{U8,U3}/unit_accuracy.csv（各 72 行）；24 个 LN 的 rsqrt_accuracy.csv；GELU 全 S11 穷举各 12×2048 个码。", "",
        "口径：Softmax 使用同一个整数 Q/K score，FP64 softmax 后按当前 output_scale ties-to-even、U3/U8 clamp。",
        "GELU 用同一 S11 输入与冻结尺度，FP32 F.gelu 后量化到 U3。LN 用同一整数输入与原 gamma/beta/epsilon，FP32 LN 后量化到 S3。",
        "码误差消除了双方共有的输出量化/裁剪误差；real_mae/real_rmse/real_max_ae 则相对于未量化、未裁剪连续参考。",
        "U3/U8 输出尺度不同，不能直接用较小 LSB MAE 或较高逐码一致率证明分类精度更好。Softmax reference_clip_rate 见全局 CSV。",
        "LN 总误差含整数均值/方差、rsqrt、仿射和输出量化，不能全称 rsqrt LUT 误差。", "",
        "三、HLS 实际执行口径与验证状态", 
        "HLS source /home/user/Desktop/FF_Vit/flash_vit_2/src_resisc45/block0.cpp:47 声明 ap_uint<3>，但 fused_flash_attn.h:89 实际读 clamp_bits=local_scalars[13]，:299/:300 是 int rq_val，:305 直接乘 V。",
        "两套历史 weights.bin 的所有 12 个 Block 对应 scalar[13] 均为 8；本次候选均为 3。二进制 Softmax scalars 位于 block*231008+78440，index13 偏移再加 52 bytes。",
        "原生 replay：image1k_hls_s3_original/src/exact.py:43 有限宽 wrap、:62 LUT 游标窄化先于 clamp、:68 LN、:84 Softmax（fused=True）、:108 可精确整数 GEMM、:360 Patch、:369 完整 forward。",
        "本次脚本 u3_validation.py:215 拟合输出尺度与倒数表，:392 逐 Block 传播 U3 并拟合 AQ，:144 限制二进制修改范围；run_experiment.py:26 全量评价，:49 局部误差。",
        "历史 U8 C-sim 冻结 fixture 的 16 边界各 490600 个整数码，在本次 CPU 与 CUDA replay 中均无差异；来源 outputs/*_u3/historical_fixture_check.json。",
        "此检查仅覆盖每套一个历史 fixture，不是新 U3 C-simulation，也不证明全数据集 RTL/板级逐码一致。",
        "新 U3：integer software = MEASURED；HLS C-sim = NOT_MEASURED；RTL cosim = NOT_MEASURED；FPGA = NOT_MEASURED。",
        "无新 bitstream/BOOT.bin、无资源/功耗/FPS实测；weights_u3.bin 是参数文件，不能当作启动文件或替换既有板卡模型。", "",
        "四、校准与工件", 
        "每套从原训练 calibration 清单确定性均匀取 256 张，排除与 val/test 内容 SHA256 相同的图像，不使用标签拟合或选择候选。",
        "每 Block 采样 2048 个完整 score 行，8192-bin 概率直方图及 128 个输出尺度候选；倒数 shift 搜索 8..24，U8 倒数存储不变；每 Block 用全部 9633792 个 A 输出码标定 AQ。",
        "局部 128 图的索引、源图 SHA256、预处理后 FP32 SHA256 与既有 LN 实验全部一致；来源各 dataset_identity.json。",
        "工件身份、软件版本、命令、全部输入文件 SHA256 见各 manifest.json；U3 软件工件 u3_artifact/{manifest.json,arrays.npz} 与 weights_u3.bin。",
        "允许改变区间为每 Block [78360,78688)，越界改动数 0；EXP 和地址进一步独立核对未变。", "",
        "五、与旧记录的不一致（保留原数据，不补造原因）", 
        "PlantVillage 论文 98.3016% 来自 5417 张 validation，本次原生 U8 重现 5325/5417；不是 5459 张 test 的数值。",
        "NWPU 历史 archive/nwpu_resisc45_ffvit/validation/final_report.md:12 记录 validation 2423/2700=89.74074074%、test 4056/4500=90.13333333%。",
        "本次冻结原生导出权重/ROM直接整数 replay 的 U8 结果见上表，与该旧软件评价计数存在差异，不能擅自写成完全重现。",
        "差异的逐样本/逐节点原因 MISSING：需按旧 reconstructed model 的相同 image ID 重跑并与本次 native replay 的 logits/中间整数码定位；一个历史 fixture 通过不足以归因。",
        "本次 U3 增减使用同一新测 native U8 作为基线，不把旧 90.1333% 与新 U3 混作严格对照。",
        "此前 U8 LUT 局部表保留不变；本次原生 ABI 新捕获结果也不静默替换旧模型路径统计。",
        "ImageNet Local4 68% 模型和现有 HLS/Vivado/bitstream 完全不在本次修改范围。", "",
        "六、结果判断", 
        "本次仅标定 U3 的全网分类精度明显下降，不能作为保留原高准确率的直接部署替代。",
        "建议保留原版本；若要恢复 U3 分类精度，需要另行批准针对同一整数/LUT合同的 QAT 或 attention-aware 标定，并冻结独立评价协议。",
        "较小的局部码域 LUT 误差与较差的全网分类精度不矛盾：局部参考已经量化/裁剪到 U3，不包含共有量化损失；端到端还受传播与 AQ 映射影响。",
        "不将全部分类精度变化归因于 EXP/倒数 LUT；尚未执行严格逐项消融。", "",
        "复算：python -B run_experiment.py --dataset plantvillage|nwpu --output 本目录内新路径 --batch-size 16；python -B summarize.py。",
        "所有新增脚本和输出仅在本独立验证目录；首次日志字段错误的失败目录已标注 FAILED_RUN，不纳入结果。"]
    (u.HERE / "report.txt").write_text("\n".join(lines)+"\n")
    print(json.dumps(dict(accuracy=accuracy,units=units),indent=2))


if __name__=="__main__":main()
