#!/usr/bin/env python3
"""Archive compact exact references and independently re-check saved Csim dumps."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.hls_csim import BOUNDARIES,sha256,verify_inventory,compare_boundaries
from src.paper_package import hls_success


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--prepare-reference',action='store_true')
    p.add_argument('--fixtures',type=Path,default=ROOT/'reports/exact_probe128_shards/fixtures')
    args=p.parse_args()
    data=ROOT/'hls/data';manifest=data/'reference_manifest.json'
    report_path=ROOT/'reports/hls_csim.json';report=json.loads(report_path.read_text())
    if not hls_success(report):raise ValueError('Csim report has not passed its complete evidence gate')
    if args.prepare_reference:
        from src.exact import load_artifact
        payload,meta=load_artifact(args.fixtures)
        if sha256(args.fixtures/'manifest.json')!=report['provenance']['fixture_manifest_sha256']:
            raise ValueError('wrong fixture identity')
        references={}
        for index in range(len(meta['ids'])):
            for _,key in BOUNDARIES.items():
                name=f'sample_{index:03d}/expected_{key}.bin'
                np.asarray(payload['traces'][key][index],dtype='<i4').tofile(data/name)
                references[name]=sha256(data/name)
        manifest.write_text(json.dumps({'fixture_ids':meta['ids'],'references':references,
            'fixture_manifest_sha256':sha256(args.fixtures/'manifest.json')},sort_keys=True,indent=2)+'\n')
    record=json.loads(manifest.read_text())
    if record['fixture_ids']!=report['provenance']['fixture_ids']:
        raise ValueError('reference IDs differ from Csim report')
    if record['fixture_manifest_sha256']!=report['provenance']['fixture_manifest_sha256']:
        raise ValueError('reference provenance differs from Csim report')
    verify_inventory({str(data/name):digest for name,digest in record['references'].items()})
    verify_inventory(report['provenance']['original_source_hashes'])
    checks=[]
    for index,sample in enumerate(report['samples']):
        traces={}
        for key in BOUNDARIES.values():
            path=data/f'sample_{index:03d}'/f'expected_{key}.bin'
            arr=np.fromfile(path,dtype='<i4')
            traces[key]=arr if key=='logits' else arr.reshape(196,192)
        result=compare_boundaries(Path(report['run_directory'])/f'sample_{index:03d}',traces)
        if result['boundaries']!=sample['boundaries'] or not result['passed']:
            raise ValueError(f'archived evidence mismatch for sample {index}')
        checks.append(result)
    audit={'passed':True,'report_sha256':sha256(report_path),'reference_manifest_sha256':sha256(manifest),
           'sample_count':len(checks),'boundary_count':len(checks)*len(BOUNDARIES),
           'checked_integer_count':sum(r['elements'] for c in checks for r in c['boundaries'].values()),
           'originals_unchanged':True,'verifier_sha256':sha256(Path(__file__))}
    (ROOT/'reports/hls_independent_audit.json').write_text(json.dumps(audit,sort_keys=True,indent=2)+'\n')
    print(json.dumps(audit,sort_keys=True))


if __name__=='__main__':main()
