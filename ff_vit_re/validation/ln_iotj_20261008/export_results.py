"""Export measured local LayerNorm evidence; never infer a hardware PASS."""
from __future__ import annotations
import argparse
import csv
import json
import math
import sys
from pathlib import Path
from capture_ln import HERE, checked_output, setup_environment, sha256

DATASETS = ('plantvillage', 'nwpu', 'imagenet')
REAL_UNITS = 'element-weighted instance-local physical output units; heterogeneous layer scales, not a common global physical norm'
METRICS = ('e07_vs_fp32_continuous', 'e07_vs_fp32_quantized', 'e07_vs_unlimited', 'actual_vs_e07', 'actual_vs_fp32_continuous')
ATTR_UNITS = {'variance_code':'input code squared / channel', 'variance_real':'local physical input units squared; heterogeneous when merged',
              'lut_rsqrt':'inverse input-code units', 'lut_rsqrt_relative':'dimensionless absolute relative error',
              'normalized_lut':'dimensionless normalized activation', 'normalized_mean':'dimensionless normalized activation'}


def merge_metrics(rows):
    n = sum(r['count'] for r in rows)
    if n <= 0:
        raise ValueError('empty metric coverage')
    result = {'count': n}
    for prefix in ('real', 'code'):
        result[prefix+'_mae'] = sum(r[prefix+'_mae']*r['count'] for r in rows)/n
        result[prefix+'_rmse'] = math.sqrt(sum(r[prefix+'_rmse']**2*r['count'] for r in rows)/n)
        result[prefix+'_maxae'] = max(r[prefix+'_maxae'] for r in rows)
    for key in ('exact_code_agreement', 'within_1_lsb'):
        result[key] = sum(r[key]*r['count'] for r in rows)/n
    return result


def validate_summary(s):
    rows, samples = s['instances'], s['sample_count']
    expected = {f'block{b:02d}.ln{n}' for b in range(12) for n in (1, 2)}
    if len(rows) != 24 or {r['name'] for r in rows} != expected:
        raise ValueError('instance coverage must be all 24 unique backbone LNs')
    if s['total_ln_tokens'] != 24*samples*196:
        raise ValueError('global token coverage mismatch')
    for r in rows:
        if r['calls'] != samples or r['tokens'] != samples*196:
            raise ValueError('instance token/image coverage mismatch')
        if any(r[k]['count'] != samples*196*192 for k in METRICS):
            raise ValueError('element coverage mismatch')
        if set(r['negative_variance_counts']) != {'wide_precast','finite_signed36','unlimited','fp32_subtractive'}:
            raise ValueError('negative variance category coverage mismatch')
        if any(v['total_count'] != r['tokens'] for v in r['negative_variance_counts'].values()):
            raise ValueError('negative variance denominator coverage mismatch')
    for k in METRICS:
        if s['global_metrics'][k]['count'] != 24*samples*196*192:
            raise ValueError('global element coverage mismatch')
    for category, counts in s['global_negative_variance_counts'].items():
        for field in ('negative_count','total_count'):
            if counts[field] != sum(r['negative_variance_counts'][category][field] for r in rows):
                raise ValueError('negative variance global reduction coverage mismatch')
    return s


def status_row(s, host):
    return {'software_equivalence':s['equivalence_status'],
            'HOST_HLS_C_MODEL':host['status'] if host else 'NOT_MEASURED',
            'VITIS_CSIM':'NOT_MEASURED', 'RTL_COSIM':'NOT_MEASURED', 'FPGA':'NOT_MEASURED',
            'classification_accuracy':'NOT_MEASURED', 'edge_latency_energy':'NOT_MEASURED'}


def flatten(value, prefix=''):
    result = {}
    for key, child in value.items():
        name = prefix+key
        if isinstance(child, dict): result.update(flatten(child, name+'.'))
        elif isinstance(child, (list,tuple)): result[name] = json.dumps(child)
        else: result[name] = child
    return result


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fields); writer.writeheader(); writer.writerows(rows)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n')


def tex(value):
    return str(value).replace('\\', r'\textbackslash{}').replace('_', r'\_').replace('%', r'\%').replace('&', r'\&').replace('#', r'\#')


def latex_table(path, headers, rows, caption, source):
    text = ['% Generated from measured JSON. Source: '+source,
            r'\begin{table*}[t]', r'\centering\scriptsize',
            r'\caption{'+caption+' '+r'\texttt{\detokenize{'+source+'}}.}',
            r'\resizebox{\textwidth}{!}{%', r'\begin{tabular}{'+'l'*len(headers)+'}', r'\hline',
            ' & '.join(headers)+r' \\', r'\hline']
    text.extend(' & '.join(map(tex,row))+r' \\' for row in rows)
    text.extend([r'\hline',r'\end{tabular}',r'}',r'\end{table*}'])
    path.write_text('\n'.join(text)+'\n')


def export_all(input_root, output_root, make_plots=True):
    setup_environment()
    input_root, out = Path(input_root).resolve(), checked_output(output_root)
    if not input_root.is_relative_to(HERE): raise ValueError('input outside validation')
    out.mkdir(parents=True,exist_ok=True); (out/'tables').mkdir(exist_ok=True)
    summaries, provenance, boundaries, hosts = {}, {}, {}, {}
    source_files = []
    for d in DATASETS:
        base = input_root/d
        for filename in ('summary.json','boundary.json','provenance.json','samples.json','command.json'):
            source_files.append(base/filename)
        summaries[d] = validate_summary(json.loads((base/'summary.json').read_text()))
        boundaries[d] = json.loads((base/'boundary.json').read_text())
        provenance[d] = json.loads((base/'provenance.json').read_text())
        samples = json.loads((base/'samples.json').read_text())
        if len(samples['samples']) != summaries[d]['sample_count'] or samples['selected_indices'] != provenance[d]['selected_indices']:
            raise ValueError('sample identity coverage mismatch')
        hp = base/'hls_host/report.json'
        hosts[d] = json.loads(hp.read_text()) if hp.exists() else None
        if hp.exists(): source_files.append(hp)
    audit_path = HERE/'outputs/source_audit.json'
    audit = json.loads(audit_path.read_text()); source_files.append(audit_path)
    instances, global_rows, stages, ranges, negatives, synthetic, bounds, attribution, cancellation = [], [], [], [], [], [], [], [], []
    def negative_rows(dataset, scope, instance, counts, case=''):
        for category, count in counts.items():
            negatives.append(dict(dataset=dataset,scope=scope,instance=instance,case=case,category=category,
                units='token variances, once per LN token',**count))
    def range_rows(dataset, scope, instance, bits, values, case=''):
        for register, item in values.items():
            ranges.append(dict(dataset=dataset,scope=scope,instance=instance,case=case,input_bits=bits,
                register=register,units='integer arithmetic units; register-specific, not output physical units',**item))
    def attribution_rows(dataset, scope, instance, values, case=''):
        for key, value in values.items():
            if isinstance(value,dict):
                attribution.append(dict(dataset=dataset,scope=scope,instance=instance,case=case,
                    component=key,units=ATTR_UNITS[key],**value))
    for d, s in summaries.items():
        for r in s['instances']:
            meta = dict(dataset=d,instance=r['name'],images=r['calls'],tokens=r['tokens'],elements=r['actual_vs_e07']['count'],
                        input_bits=r['input_bits'],input_scale=r['input_scale'],output_scale=r['output_scale'],eps=r['eps'],
                        real_units='local physical output units',code_units='integer output LSB')
            instances.append({**meta,**flatten({k:r[k] for k in METRICS})})
            range_rows(d,'SAMPLED',r['name'],r['input_bits'],r['ranges'])
            negative_rows(d,'SAMPLED',r['name'],r['negative_variance_counts'])
            attribution_rows(d,'SAMPLED',r['name'],r['attribution'])
            cancellation.append(dict(dataset=d,scope='SAMPLED',instance=r['name'],case='',
                integer_identity_mismatches=r['integer_variance_identity_mismatches'],
                cancellation_ratio_max=r['attribution']['variance_cancellation_ratio_max'],
                units='FP32 counterfactual error: input-code squared channel sum',
                **r['counterfactual_fp32_subtractive_vs_float64_central_varsum']))
        negative_rows(d,'SAMPLED','GLOBAL',s['global_negative_variance_counts'])
        attribution_rows(d,'SAMPLED','GLOBAL',s['global_attribution'])
        for bits, rs in s['global_ranges_by_input_width'].items(): range_rows(d,'SAMPLED','GLOBAL_WIDTH_'+bits,int(bits),rs)
        for key, m in s['global_metrics'].items(): global_rows.append(dict(dataset=d,comparison=key,real_units=REAL_UNITS,code_units='integer output LSB',**m))
        for stage in ('ln1','ln2'):
            selected = [r for r in s['instances'] if r['name'].endswith(stage)]
            for key in METRICS:
                stages.append(dict(dataset=d,stage=stage,comparison=key,real_units=REAL_UNITS,code_units='integer output LSB',
                                   **merge_metrics([r[key] for r in selected])))
        boundary = boundaries[d]
        negative_rows(d,'SYNTHETIC','GLOBAL',boundary['global_negative_variance_counts'])
        for r in boundary['instances']:
            bits = r['bounds']['input_bits']; bounds.append(dict(dataset=d,instance=r['name'],**r['bounds']))
            negative_rows(d,'SYNTHETIC',r['name'],r['negative_variance_counts'])
            for case, c in r['cases'].items():
                synthetic.append(dict(dataset=d,instance=r['name'],case=case,tokens=c['tokens'],
                    input_bits=bits,finite_mean=json.dumps(c['finite_mean']),unlimited_mean=json.dumps(c['unlimited_mean']),
                    finite_variance=json.dumps(c['finite_variance']),unlimited_variance=json.dumps(c['unlimited_variance']),
                    **flatten(c['finite_vs_unlimited']),scope='SYNTHETIC ONLY, exported final parameters'))
                range_rows(d,'SYNTHETIC',r['name'],bits,c['ranges'],case)
                negative_rows(d,'SYNTHETIC',r['name'],c['negative_variance_counts'],case)
                attribution_rows(d,'SYNTHETIC',r['name'],c['attribution'],case)
                cancellation.append(dict(dataset=d,scope='SYNTHETIC',instance=r['name'],case=case,
                    integer_identity_mismatches=c['counterfactual']['integer_identity_mismatches'],
                    cancellation_ratio_max=c['attribution']['variance_cancellation_ratio_max'],
                    units=c['counterfactual']['units'],**c['counterfactual']['fp32_subtractive_vs_float64_central_varsum']))
    all_metrics = {k:merge_metrics([s['global_metrics'][k] for s in summaries.values()]) for k in METRICS}
    all_negative = {}
    for scope, groups in [('SAMPLED',[s['global_negative_variance_counts'] for s in summaries.values()]),
                          ('SYNTHETIC',[b['global_negative_variance_counts'] for b in boundaries.values()])]:
        counts = {key:{field:sum(g[key][field] for g in groups) for field in ('negative_count','total_count')}
                  for key in ('wide_precast','finite_signed36','unlimited','fp32_subtractive')}
        all_negative[scope] = counts
        negative_rows('ALL',scope,'GLOBAL',counts)
    for key, m in all_metrics.items(): global_rows.append(dict(dataset='ALL',comparison=key,real_units=REAL_UNITS,code_units='integer output LSB',**m))
    statuses = {d:status_row(summaries[d],hosts[d]) for d in DATASETS}
    result = dict(scope='deterministic held-out sampled local LN audit; no full-domain inference',
        datasets={d:dict(images=s['sample_count'],instances=24,tokens=s['total_ln_tokens'],
                        metrics=s['global_metrics'],negative_variance_counts=s['global_negative_variance_counts']) for d,s in summaries.items()},
        all_datasets=all_metrics,all_negative_variance_counts=all_negative,
        real_units=REAL_UNITS,code_units='integer output LSB',status_matrix=statuses,
        references=summaries['plantvillage']['reference_definitions'],
        negative_variance_definitions=summaries['plantvillage']['negative_variance_definitions'])
    write_json(out/'global_summary.json', result)
    for filename, rows in [('per_instance.csv',instances),('global_summary.csv',global_rows),('per_stage.csv',stages),
                           ('dynamic_ranges.csv',ranges),('negative_variance_counts.csv',negatives),
                           ('synthetic_boundaries.csv',synthetic),('mathematical_bounds.csv',bounds),
                           ('attribution.csv',attribution),('variance_cancellation.csv',cancellation),
                           ('status_matrix.csv',[dict(dataset=d,**s) for d,s in statuses.items()])]: write_csv(out/filename,rows)
    for d in DATASETS: write_csv(out/f'per_instance_{d}.csv',[r for r in instances if r['dataset']==d])
    inventory = [dict(path='E07 fixed_head_layernorm',note=audit['head']['actual'],numeric_status='NOT_MEASURED',included_in_24=False)]
    inventory += [dict(path=r['path'],note=r['note'],numeric_status='MEASURED_AS_BACKBONE_ROUTE' if r['executed_for_24'] else 'NOT_MEASURED',included_in_24=r['executed_for_24']) for r in audit['other_ln_inventory']]
    write_csv(out/'other_ln_inventory.csv',inventory)
    freeze = {}
    for d,p in provenance.items():
        records={r['path']:r['sha256'] for r in p['files']}
        records.update(p.get('source_binding_verification',{}).get('sources',{}))
        changed=[path for path, digest in records.items() if sha256(path)!=digest]
        freeze[d]=dict(status='FAIL' if changed else 'PASS',files_checked=len(records),changed=changed)
    source_records = audit['sources']
    if isinstance(source_records,dict): source_records=list(source_records.values())
    changed=[r['path'] for r in source_records if sha256(r['path'])!=r['sha256']]
    freeze['source_audit']=dict(status='FAIL' if changed else 'PASS',files_checked=len(source_records),changed=changed)
    write_json(out/'source_freeze_verification.json',freeze)
    write_json(out/'evidence_manifest.json',dict(inputs=[dict(path=str(p),sha256=sha256(p)) for p in source_files],
        historical_evidence=[dict(path=r.get('path'),classification=r['classification']) for r in audit['historical_evidence']],
        historical_policy='retained as historical evidence only; no current PASS inferred'))
    src=str(input_root.relative_to(HERE))
    compact=[]
    for d,s in summaries.items():
        m=s['global_metrics']['e07_vs_fp32_continuous']
        compact.append([d,s['sample_count'],m['count'],f"{m['code_mae']:.6g}",f"{m['code_rmse']:.6g}",m['code_maxae'],
                        f"{100*m['exact_code_agreement']:.5f}%",f"{100*m['within_1_lsb']:.5f}%",
                        f"{m['real_mae']:.6g}",f"{m['real_rmse']:.6g}",f"{m['real_maxae']:.6g}"])
    latex_table(out/'tables/global_metrics.tex',['Dataset','Images','Codes','MAE (LSB)','RMSE (LSB)','MaxAE (LSB)','Exact','Within 1 LSB','MAE (real)','RMSE (real)','MaxAE (real)'],compact,
        'Sampled local E07 versus FP32; real errors mix layer-local physical scales. Code agreement uses quantized FP32. Not classification accuracy.',src+'/*/summary.json')
    for d in DATASETS:
        rows=[]
        for r in summaries[d]['instances']:
            m=r['e07_vs_fp32_continuous']
            rows.append([r['name'],r['calls'],r['tokens'],m['count'],f"{m['code_mae']:.5g}",f"{m['code_rmse']:.5g}",m['code_maxae'],
                         f"{100*m['exact_code_agreement']:.4f}%",f"{100*m['within_1_lsb']:.4f}%",f"{m['real_mae']:.5g}",f"{m['real_rmse']:.5g}",f"{m['real_maxae']:.5g}"])
        latex_table(out/f'tables/per_instance_{d}.tex',['LN','Images','Tokens','Codes','MAE (LSB)','RMSE (LSB)','Max (LSB)','Exact','Within 1 LSB','MAE (real)','RMSE (real)','Max (real)'],rows,
            d+': all 24 logical LNs; real units are local to each instance.',src+'/'+d+'/summary.json')
    latex_table(out/'tables/negative_variance.tex',['Dataset','Scope','Wide / tokens','Signed36 / tokens','Unlimited / tokens','FP32 subtractive / tokens'],
        [[d,scope]+[f"{obj[k]['negative_count']}/{obj[k]['total_count']}" for k in ('wide_precast','finite_signed36','unlimited','fp32_subtractive')]
         for d in DATASETS for scope,obj in [('SAMPLED',summaries[d]['global_negative_variance_counts']),('SYNTHETIC',boundaries[d]['global_negative_variance_counts'])]],
        'Negative variance counts; denominator counts LN-token variances, not channels. FP32 subtractive is counterfactual.',src+'/*/{summary,boundary}.json')
    br=[]
    for d in DATASETS:
        for bits in (13,15):
            group=[r for r in bounds if r['dataset']==d and r['input_bits']==bits]
            br.append([d,bits,len(group),sum(r['mean_product32_full_domain_sufficient'] for r in group),
                sum(r['variance36_full_domain_sufficient'] for r in group),sum(r['affine40_full_domain_sufficient'] for r in group),
                max(r['variance_sum_upper_bound'] for r in group),max(r['affine_abs_upper_bound'] for r in group)])
    latex_table(out/'tables/mathematical_bounds.tex',['Dataset','Input bits','LNs','Mean32 sufficient','Var36 sufficient','Affine40 sufficient','Var upper bound','Affine upper bound'],br,
        'Counts of conservative sufficient full-domain bounds with actual exported parameters; false sufficiency is not observed overflow. Limits: signed36=34359738367; signed40=549755813887.',src+'/*/boundary.json')
    latex_table(out/'tables/validation_status.tex',['Dataset','Software','Host HLS C model','Vitis CSIM','RTL cosim','FPGA'],
        [[d]+[statuses[d][k] for k in ('software_equivalence','HOST_HLS_C_MODEL','VITIS_CSIM','RTL_COSIM','FPGA')] for d in DATASETS],
        'Current experiment status. Host execution uses unchanged header and reduced T4; it is separate from official Vitis CSIM.',src+'/*/{summary,hls_host/report}.json')
    latex_table(out/'tables/attribution.tex',['Dataset','Var MAE (code squared)','Mean norm MAE','LUT norm MAE','LUT relative MAE','Cancellation max'],
        [[d]+[f'{v:.6g}' for v in (summaries[d]['global_attribution']['variance_code']['mae'],
             summaries[d]['global_attribution']['normalized_mean']['mae'],summaries[d]['global_attribution']['normalized_lut']['mae'],
             summaries[d]['global_attribution']['lut_rsqrt_relative']['mae'],summaries[d]['global_attribution']['variance_cancellation_ratio_max'])] for d in DATASETS],
        'Sampled attribution before affine/output quantization. Mean and LUT normalized errors are dimensionless; variance error is input-code squared per channel. Contributions are not an additive output-error decomposition.',src+'/*/summary.json')
    dr=[]
    for d in DATASETS:
        for bits,rs in summaries[d]['global_ranges_by_input_width'].items():
            dr.append([d,bits]+[f"[{rs[k]['pre_min']},{rs[k]['pre_max']}]" for k in ('S','S_sq','mu','Var_sum','affine')]+
                      [sum(v['wrap_count'] for v in rs.values()),rs['output_clip']['saturation_count']])
    latex_table(out/'tables/dynamic_ranges.tex',['Dataset','Input bits','S','S squared','Mean','Var sum','Affine','Wrap events','Output clips'],dr,
        r'Sampled pre-cast integer ranges by input width. Detailed 2muS, Cmu2, mean product, diff and cursor ranges are in dynamic\_ranges.csv. Output clipping is not accumulator overflow.',src+'/*/summary.json')
    latex_table(out/'tables/quantized_fp32.tex',['Dataset','MAE (local real)','RMSE (local real)','MaxAE (local real)'],
        [[d]+[f"{summaries[d]['global_metrics']['e07_vs_fp32_quantized'][k]:.7g}" for k in ('real_mae','real_rmse','real_maxae')] for d in DATASETS],
        'E07 versus quantized local FP32 removes continuous-reference output rounding error; remaining error includes exported mapping, LUT, affine/shift and clipping effects. Element-weighted heterogeneous local physical units.',src+'/*/summary.json')
    latex_table(out/'tables/other_ln_inventory.tex',['Implementation','Included in 24 route','Numerical status'],
        [[Path(r['path']).name,r['included_in_24'],r['numeric_status']] for r in inventory],
        r'Appendix inventory; an inspected source does not inherit numerical PASS from the measured backbone. Exact paths and notes: other\_ln\_inventory.csv.',
        'outputs/source_audit.json')
    if make_plots:
        dependency_dir = HERE/'cache/export_dependencies'
        if dependency_dir.exists(): sys.path.insert(0,str(dependency_dir))
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        (out/'plots').mkdir(exist_ok=True)
        fig,axes=plt.subplots(3,2,figsize=(11,10),sharex=True)
        for i,d in enumerate(DATASETS):
            for stage in ('ln1','ln2'):
                rs=[r for r in summaries[d]['instances'] if r['name'].endswith(stage)]
                for j,key in enumerate(('code_mae','code_maxae')):
                    axes[i,j].plot(range(1,13),[r['e07_vs_fp32_continuous'][key] for r in rs],marker='o',label=stage)
                    axes[i,j].set_ylabel(d+' '+key+' (LSB)'); axes[i,j].grid(alpha=.3)
                    axes[i,j].legend()
            axes[i,0].set_title('E07 vs locally quantized FP32: MAE')
            axes[i,1].set_title('E07 vs locally quantized FP32: maximum error')
        axes[2,0].set_xlabel('Block (1-based)'); axes[2,1].set_xlabel('Block (1-based)')
        fig.suptitle('Deterministic sampled local LN outputs; not classification accuracy')
        fig.tight_layout(); fig.savefig(out/'plots/blockwise_error.pdf'); fig.savefig(out/'plots/blockwise_error.png',dpi=180); plt.close(fig)
    write_json(out/'artifact_manifest.json',dict(files=[dict(path=str(p.relative_to(out)),sha256=sha256(p),bytes=p.stat().st_size)
        for p in sorted(out.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json']))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=HERE/'outputs/final128')
    parser.add_argument('--output',type=Path,default=HERE/'outputs/paper')
    args=parser.parse_args()
    result=export_all(args.input,args.output)
    print(json.dumps(dict(output=str(args.output.resolve()),instances=72,
        compared_codes=result['all_datasets']['actual_vs_e07']['count'],status_matrix=result['status_matrix'])))


if __name__=='__main__': main()
