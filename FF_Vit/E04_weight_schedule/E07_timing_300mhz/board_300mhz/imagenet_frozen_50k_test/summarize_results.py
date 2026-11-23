"""Independently recompute frozen-E07 board accuracy from saved S19 logits."""
import argparse
import csv
import json
import struct
from pathlib import Path

import numpy as np


def summarize(results,dataset):
    results,dataset=Path(results),Path(dataset)
    idx=(dataset/"INDEX.BIN").read_bytes()
    if len(idx)<32: raise ValueError("short index")
    magic,version,count,frame_bytes,chunk_frames,record_bytes,reserved=struct.unpack_from("<8s6I",idx)
    if (magic,version,frame_bytes,record_bytes,reserved)!=(b"IM1KE07\0",1,301056,12,0) or not 1<=count<=50000:
        raise ValueError("wrong index header")
    if len(idx)!=32+12*count: raise ValueError("wrong index size")
    records=np.frombuffer(idx,dtype="<u4",offset=32).reshape(count,3)
    if not np.array_equal(records[:,0],np.arange(count)) or np.any(records[:,1]>=1000):
        raise ValueError("invalid index identities or labels")
    meta=dict(line.split("=",1) for line in (results/"ACCSUM.TXT").read_text().splitlines() if "=" in line)
    if meta.get("BOARD_EVALUATION_COMPLETE")!="YES" or int(meta["COMPLETED_FRAMES"])!=count or \
        int(meta["REQUESTED_FRAMES"])!=count or int(meta["FAILED_FRAMES"])!=0:
        raise ValueError("partial or failed board run")
    with (results/"RESULT.CSV").open(newline="") as stream:
        rows=list(csv.DictReader(stream))
    if len(rows)!=count: raise ValueError("partial CSV")
    path=results/"LOGITS.BIN"
    if path.stat().st_size!=count*4000: raise ValueError("partial logits")
    logits=np.fromfile(path,dtype="<i4").reshape(count,1000)
    if np.any(logits < -262144) or np.any(logits>262143): raise ValueError("logits outside S19")
    top=np.argsort(-logits,axis=1,kind="stable")[:,:5]
    c1=c5=ticks=0
    per_ticks=[]
    for i,row in enumerate(rows):
        if int(row["index"])!=i or int(row["label"])!=int(records[i,1]) or \
            int(row["input_crc32"],16)!=int(records[i,2]):
            raise ValueError("sample/label/input identity mismatch")
        observed=[int(row[f"pred{k}"]) for k in range(1,6)]
        if observed!=top[i].tolist(): raise ValueError("CSV predictions disagree with raw logits")
        hit1=int(top[i,0]==records[i,1]); hit5=int(records[i,1] in top[i])
        if int(row["correct1"])!=hit1 or int(row["correct5"])!=hit5:
            raise ValueError("CSV correctness flags disagree")
        t=int(row["inference_ticks"])
        if t<=0: raise ValueError("nonpositive timing")
        c1+=hit1; c5+=hit5; ticks+=t; per_ticks.append(t)
    if c1!=int(meta["TOP1_CORRECT"]) or c5!=int(meta["TOP5_CORRECT"]) or ticks!=int(meta["INFERENCE_TICKS"]):
        raise ValueError("summary counts or timing disagree with independent recomputation")
    hz=int(meta["TIMER_HZ"]); wall=int(meta["DATASET_WALL_TICKS"])
    if hz<=0 or wall<ticks: raise ValueError("invalid wall clock")
    per_ms=np.asarray(per_ticks,dtype=np.float64)*1000/hz
    return {"model":"current frozen E07; no other ImageNet QAT model parameters loaded",
        "frames":count,"full_imagenet_50k":count==50000,"top1_correct":c1,"top5_correct":c5,
        "top1_percent":100*c1/count,"top5_percent":100*c5/count,
        "inference_fps_excluding_sd_and_logging":count*hz/ticks,
        "dataset_wall_fps_including_sd_and_logging":count*hz/wall,
        "average_inference_ms":float(per_ms.mean()),"inference_ms_std_population":float(per_ms.std()),
        "inference_ms_min":float(per_ms.min()),"inference_ms_max":float(per_ms.max()),
        "classes_present":int(len(np.unique(records[:,1]))),
        "verification":"all logits, Top5, labels, input CRCs, counts and timing independently reconciled"}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results",type=Path,help="directory copied back from SD with RESULT.CSV, LOGITS.BIN, ACCSUM.TXT")
    parser.add_argument("--dataset",type=Path,default=Path(__file__).resolve().parent/"deploy")
    parser.add_argument("--out",type=Path)
    args=parser.parse_args()
    report=summarize(args.results,args.dataset)
    text=json.dumps(report,indent=2)
    print(text)
    if args.out:
        with args.out.open("x") as f: f.write(text+"\n")
