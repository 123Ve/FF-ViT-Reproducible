"""Stream 24 local LN traces into scalar reductions, with isolated workers."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
import ln_numeric as ln
from capture_ln import HERE, Adapter, checked_output, setup_environment


def write_json(path, value):
    path = checked_output(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def variance_counterfactual(x):
    """Code-domain varsum; FP32 counterfactual is not the integer implementation."""
    x = np.asarray(x, dtype=np.int64)
    s = x.sum(-1); mu = s // x.shape[-1]
    a = (x*x).sum(-1)-2*mu*s+x.shape[-1]*mu*mu
    b = ((x-mu[:,None])**2).sum(-1)
    f = x.astype(np.float32); mf = f.mean(-1)
    subtractive = (f*f).sum(-1) - np.float32(x.shape[-1])*mf*mf
    d = x.astype(np.float64); central = ((d-d.mean(-1,keepdims=True))**2).sum(-1)
    err = ln.ErrorAccumulator(); err.update(subtractive, central)
    return dict(integer_identity_mismatches=int(np.count_nonzero(a != b)),
                integer_identity_mean='floor exact mean; identity holds for any integer mean, before casts',
                fp32_subtractive_vs_float64_central_varsum=err.summary(),
                units='integer input code squared, channel sum; counterfactual FP32 arithmetic')


def merge_negative_variance_counts(rows):
    result={key:dict(negative_count=0,total_count=0) for key in
            ('wide_precast','finite_signed36','unlimited','fp32_subtractive')}
    for row in rows:
        for key in result:
            for field in result[key]: result[key][field]+=int(row[key][field])
    return result


def negative_variance_counts(x,batch):
    f=np.asarray(x,dtype=np.float32); mean=f.mean(-1)
    values={'wide_precast':batch['e07']['variance_wide'],
            'finite_signed36':batch['e07']['variance'],
            'unlimited':batch['unlimited']['variance'],
            'fp32_subtractive':(f*f).sum(-1)-np.float32(f.shape[-1])*mean*mean}
    return {key:dict(negative_count=int(np.count_nonzero(value<0)),total_count=int(value.size))
            for key,value in values.items()}


class InstanceAccumulator:
    def __init__(self, name, params, bits, gamma, beta, sx, sy, eps, output):
        self.name, self.params, self.bits = name, params, bits
        self.gamma, self.beta, self.sx, self.sy, self.eps = gamma, beta, sx, sy, eps
        self.output = checked_output(output)
        self.metrics = {k: ln.MetricAccumulator() for k in ('e07_vs_fp32_continuous', 'e07_vs_fp32_quantized',
                       'e07_vs_unlimited', 'actual_vs_e07', 'actual_vs_fp32_continuous')}
        self.ranges, self.attribution = ln.RangeAccumulator(), ln.AttributionAccumulator()
        self.tokens, self.calls, self.mismatches = 0, 0, 0
        self.counterfactual = ln.ErrorAccumulator(); self.identity_mismatches = 0
        self.negative_variance_counts=merge_negative_variance_counts([])

    def compare(self, x):
        return ln.compare_batch(x, self.params, input_bits=self.bits, gamma=self.gamma, beta=self.beta,
                                input_scale=self.sx, output_scale=self.sy, eps=self.eps)

    def update(self, x, actual, identity):
        x, actual = np.asarray(x), np.asarray(actual)
        if x.shape != actual.shape: raise ValueError('capture shape mismatch')
        batch = self.compare(x); e, u, fp = (batch[k] for k in ('e07', 'unlimited', 'fp32'))
        pairs = {'e07_vs_fp32_continuous': (e['real'], fp['real'], e['codes'], fp['codes']),
                 'e07_vs_fp32_quantized': (e['real'], fp['codes']*self.sy, e['codes'], fp['codes']),
                 'e07_vs_unlimited': (e['real'], u['real'], e['codes'], u['codes']),
                 'actual_vs_e07': (actual*self.sy, e['real'], actual, e['codes']),
                 'actual_vs_fp32_continuous': (actual*self.sy, fp['real'], actual, fp['codes'])}
        for key, args in pairs.items(): self.metrics[key].update(*args)
        self.ranges.update(e['diagnostics']); self.attribution.update(batch)
        self.negative_variance_counts=merge_negative_variance_counts(
            [self.negative_variance_counts,negative_variance_counts(x,batch)])
        self.tokens += x.shape[0]; self.calls += 1
        mismatches = int(np.count_nonzero(actual != e['codes']))
        if mismatches and not self.mismatches:
            np.savez_compressed(self.output / f'mismatch_{self.name}.npz', x=x, actual=actual,
                                e07=e['codes'], identity=np.array(identity), **self.params)
        self.mismatches += mismatches
        f = x.astype(np.float32); mean = f.mean(-1)
        sub = (f*f).sum(-1)-np.float32(x.shape[-1])*mean*mean
        d = x.astype(np.float64); center = ((d-d.mean(-1,keepdims=True))**2).sum(-1)
        self.counterfactual.update(sub, center)
        mu = u['mean']; s = x.sum(-1)
        self.identity_mismatches += int(np.count_nonzero((x*x).sum(-1)-2*mu*s+x.shape[-1]*mu*mu != ((x-mu[:,None])**2).sum(-1)))
        if self.calls == 1:
            fixture = self.output / 'fixtures'; fixture.mkdir(exist_ok=True)
            np.savez_compressed(fixture / f'{self.name}.npz', x=x[:4], actual=actual[:4], e07=e['codes'][:4],
                gamma=self.gamma, beta=self.beta, sx=self.sx, sy=self.sy, eps=self.eps, bits=self.bits,
                identity=np.array(identity), **self.params)

    def summary(self):
        metrics = {k:v.summary() for k,v in self.metrics.items()}
        metrics['actual_vs_e07'].update(status='FAIL' if self.mismatches else ('PASS' if self.tokens else 'NOT_MEASURED'), mismatch_codes=self.mismatches)
        return dict(name=self.name, tokens=self.tokens, calls=self.calls, input_bits=self.bits,
                    input_scale=self.sx, output_scale=self.sy, eps=self.eps, missing_fields=[],
                    metrics_units='real_* in local physical output units; code_* in integer output LSB',
                    ranges=self.ranges.summary(), attribution=self.attribution.summary(),
                    negative_variance_counts=self.negative_variance_counts,
                    integer_variance_identity_mismatches=self.identity_mismatches,
                    counterfactual_fp32_subtractive_vs_float64_central_varsum=self.counterfactual.summary(), **metrics)

    def boundaries(self):
        hi, lo = (1 << (self.bits-1))-1, -(1 << (self.bits-1))
        high = np.full((4,192), 3000, dtype=np.int64); high[1,0] += 1
        high[2:] = hi-1; high[3,0] += 1
        extrema = np.stack([np.full(192,lo), np.full(192,hi), np.tile([lo,hi],96), np.tile([hi,lo],96)])
        cases = {}
        for label,x in [('high_mean_low_variance',high), ('extrema',extrema)]:
            batch = self.compare(x); e,u,fp = (batch[k] for k in ('e07','unlimited','fp32'))
            metric = ln.MetricAccumulator(); metric.update(e['real'], u['real'], e['codes'],u['codes'])
            attr = ln.AttributionAccumulator(); attr.update(batch)
            cases[label] = dict(tokens=4, finite_vs_unlimited=metric.summary(), ranges=e['diagnostics'],
                negative_variance_counts=negative_variance_counts(x,batch),
                finite_mean=e['mean'].tolist(), unlimited_mean=u['mean'].tolist(),
                finite_variance=e['variance'].tolist(), unlimited_variance=u['variance'].tolist(),
                attribution=attr.summary(), counterfactual=variance_counterfactual(x))
            folder=self.output/'fixtures'; folder.mkdir(exist_ok=True)
            np.savez_compressed(folder / f'{self.name}.{label}.npz', x=x, e07=e['codes'], bits=self.bits, **self.params)
        return dict(name=self.name, scope='SYNTHETIC, actual final export parameters; not sampled-data evidence',
                    bounds=ln.mathematical_bounds(self.params, input_bits=self.bits), cases=cases,
                    negative_variance_counts=merge_negative_variance_counts(
                        [case['negative_variance_counts'] for case in cases.values()]))


def merge_ranges_by_input_width(accumulators):
    groups = {}
    for a in accumulators:
        groups.setdefault(str(a.bits), ln.RangeAccumulator()).merge(a.ranges)
    return {k: v.summary() for k, v in groups.items()}


def worker(dataset, samples, output):
    start=time.monotonic(); adapter=Adapter(dataset, output, samples)
    accumulators = {s['name']: InstanceAccumulator(s['name'], s['params'], s['bits'], s['gamma'], s['beta'],
                     s['sx'], s['sy'], s['eps'], output) for s in adapter.specs}
    if len(accumulators) != 24: raise ValueError('expected all 24 backbone LNs')
    write_json(output/'provenance.json', adapter.provenance)
    adapter.run(lambda spec,x,actual,identity: accumulators[spec['name']].update(x,actual,identity))
    rows=[a.summary() for a in accumulators.values()]
    expected=samples*196
    if any(row['tokens'] != expected or row['calls'] != samples for row in rows):
        raise ValueError('capture coverage is incomplete')
    global_metrics={}
    for key in next(iter(accumulators.values())).metrics:
        merged=ln.MetricAccumulator()
        for a in accumulators.values(): merged.merge(a.metrics[key])
        global_metrics[key]=merged.summary()
    ranges=merge_ranges_by_input_width(accumulators.values()); attribution=ln.AttributionAccumulator()
    for a in accumulators.values(): attribution.merge(a.attribution)
    status='FAIL' if any(a.mismatches for a in accumulators.values()) else 'PASS'
    write_json(output/'samples.json',dict(selected_indices=adapter.indices, samples=adapter.records))
    boundaries=[a.boundaries() for a in accumulators.values()]
    write_json(output/'boundary.json',dict(scope='SYNTHETIC ONLY',instances=boundaries,
        global_negative_variance_counts=merge_negative_variance_counts([b['negative_variance_counts'] for b in boundaries])))
    summary=dict(schema='ln.validation.v1',dataset=dataset, sample_count=samples, instances=rows,
                 scope='deterministic held-out sample only; no full-dataset safety proof or accuracy evaluation',
                 equivalence_status=status, global_metrics=global_metrics, global_ranges_by_input_width=ranges,
                 global_attribution=attribution.summary(), total_ln_tokens=sum(a.tokens for a in accumulators.values()),
                 global_negative_variance_counts=merge_negative_variance_counts([a.negative_variance_counts for a in accumulators.values()]),
                 negative_variance_definitions={'wide_precast':'finite-path signed64 variance_wide before signed36 assignment',
                    'finite_signed36':'finite signed36 Var_sum', 'unlimited':'unlimited integer variance',
                    'fp32_subtractive':'counterfactual FP32 sum(x*x)-C*mean(x)*mean(x), input code squared; not executed integer path',
                    'denominator':'total_count counts token variances, once per token and LN'},
                 reference_definitions={'fp32':'continuous NumPy FP32 local LN on dequantized captured integer input',
                 'unlimited':'same exported scalars/LUT/shifts/clipping with unbounded integer intermediates',
                 'e07':'Task1 finite-width E07 source arithmetic; host native int overflow assumes -fwrapv',
                 'actual':'unmodified dataset-specific existing integer runtime output',
                 'global_real_units':'element-weighted across instance-local physical units/scales; heterogeneous layer units'},
                 missing_fields=[], statuses={'software_equivalence':status,'VITIS_CSIM':'NOT_MEASURED','RTL_COSIM':'NOT_MEASURED','FPGA':'NOT_MEASURED'},
                 elapsed_seconds=time.monotonic()-start)
    write_json(output/'summary.json',summary)
    print(json.dumps(dict(dataset=dataset,status=status,ln_instances=24,total_ln_tokens=summary['total_ln_tokens'],elapsed_seconds=summary['elapsed_seconds'])),flush=True)
    return 0 if status=='PASS' else 2


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',choices=['plantvillage','nwpu','imagenet','all'],required=True)
    parser.add_argument('--samples',type=int,default=128)
    parser.add_argument('--output',type=Path,default=HERE/'outputs')
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args(); setup_environment()
    out=checked_output(args.output); out.mkdir(parents=True,exist_ok=True)
    if args.worker:
        if args.dataset=='all': parser.error('worker accepts one dataset')
        raise SystemExit(worker(args.dataset,args.samples,out))
    datasets=['plantvillage','nwpu','imagenet'] if args.dataset=='all' else [args.dataset]
    codes=[]
    for dataset in datasets:
        destination=out/dataset; destination.mkdir(parents=True,exist_ok=True)
        cmd=[sys.executable,'-B',str(Path(__file__).resolve()),'--worker','--dataset',dataset,'--samples',str(args.samples),'--output',str(destination)]
        write_json(destination/'command.json',dict(argv=cmd,cwd=str(HERE),environment={k:v for k,v in os.environ.items() if k in ('PYTHONDONTWRITEBYTECODE','OMP_NUM_THREADS','MKL_NUM_THREADS','TMPDIR','XDG_CACHE_HOME','TORCH_HOME','HF_HOME','MPLCONFIGDIR','TRITON_CACHE_DIR')}))
        with (destination/'run.log').open('w') as log:
            result=subprocess.run(cmd,cwd=HERE,env=os.environ.copy(),stdout=log,stderr=subprocess.STDOUT)
        print(json.dumps(dict(dataset=dataset,returncode=result.returncode,log=str(destination/'run.log'))),flush=True)
        codes.append(result.returncode)
    raise SystemExit(max(codes))


if __name__=='__main__': main()
