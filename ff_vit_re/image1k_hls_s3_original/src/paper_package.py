"""Small, deterministic gates for publication-stage aggregation."""
from .hls_csim import BOUNDARIES


def hls_success(report):
    if not (report.get('passed') and report.get('status')=='PASS'
            and report.get('vitis_returncode')==0 and report.get('originals_unchanged')):
        return False
    rows=report.get('samples',[])
    if len(rows)!=4 or len({r.get('sample_id') for r in rows})!=4:return False
    for row in rows:
        if not row.get('passed') or row.get('returncode')!=0:return False
        boundaries=row.get('boundaries',{})
        if set(boundaries)!=set(BOUNDARIES.values()):return False
        for name,stats in boundaries.items():
            if stats.get('elements')!=(1000 if name=='logits' else 196*192):return False
            if stats.get('mismatch_count')!=0 or stats.get('max_abs_error')!=0:return False
    return True


def validate_sensitivity(report,count):
    rows=report['records']
    if len({row['experiment_id'] for row in rows})!=len(rows):
        raise ValueError('duplicate sensitivity case')
    if len(rows)!=count or any(row['sample_count']!=50000 for row in rows):
        raise ValueError('sensitivity count or formal sample count mismatch')


def formal_stage(name,record,kind):
    if record.get('sample_count') != 50000:
        raise ValueError('formal accuracy requires 50000 samples')
    return {'stage':name,'kind':kind,'sample_count':50000,
            'top1_percent':round(record['top1']*100,6),
            'top5_percent':round(record['top5']*100,6)}


def completeness(inputs):
    missing=[]
    for family,count in (('operator',17),('layer',36),('cumulative',24)):
        if inputs.get(family)!=count:missing.append(family+'_sensitivity')
    if inputs.get('sensitivity_version')!=2:missing.append('sensitivity_v2')
    if not inputs.get('exact50k'):missing.append('exact50k')
    if not inputs.get('hls_passed') or inputs.get('hls_sample_count',0)<4:missing.append('hls_bit_exact')
    return {'complete':not missing,'missing':missing}
