"""Fail-closed offline analysis of schema-1 exports (Python3.11+, stdlib).

Energy uses the shared board window and actual Power-register read intervals.
Host FPS/E2E remain in host monotonic time. Synthetic fixtures are never physical
measurements. Coverage does not establish unbiased sampling or accuracy.
"""
import argparse
import csv
import hashlib
import json
import math
import pathlib
import re
import statistics
import struct
import sys
sys.dont_write_bytecode=True

if __package__:
    from . import collect, wire, profiles, load
else:
    sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
    from host import collect, wire, profiles, load

ROOT=pathlib.Path(__file__).resolve().parents[1]
QUALIFICATIONS=[
    'Diagnostic capture uses at least30s warmup; thermal steady state is not assumed. The warmup qualification does not prove stationarity of the complete measurement window.',
    '35.2 ms nominal bus+shunt ADC averaging interval; read midpoint is an observation-time convention.',
    'Power read begin/end are preserved; ADC update phase and boundary uncertainty remain unresolved.',
    'CVRF is a readiness observation, not an exact conversion sequence or independent-sample count.',
    'Read/inference overlap and complete coverage do not prove unbiased sampling or instrument accuracy.',
    'Rshunt values and Power LSB are configured values, not a new physical calibration.',
    'A53-1 sampler/core activity is included in candidate-image rail power; it is not calibrated away or evidence of old single-core workload power.',
    'Repetition sample SD describes this setup, not instrument accuracy or independent power-on restarts.',
    'Full/Compact business functions differ; power changes are not matched-service savings.',
    '120 FPS is offered cloud input, not guaranteed completed throughput or PL continuous operation.',
    'No old 9.506 W/5.855 W value is combined with this dataset; no positive saving is presumed.'
]


class AnalysisError(RuntimeError):
    """Corrupt, inconsistent, or missing evidence; no derived report is written."""


class IdentityError(AnalysisError,collect.IdentityError):
    """A binding mismatch prevents derived output."""


def unique_pairs(items):
    value={}
    for key,item in items:
        if key in value:raise AnalysisError('duplicate JSON key: '+key)
        value[key]=item
    return value


def read_json(path):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding='utf-8'),object_pairs_hook=unique_pairs,
            parse_constant=lambda x:(_ for _ in ()).throw(AnalysisError('nonfinite JSON')))
    except (OSError,ValueError,UnicodeError) as exc:
        raise AnalysisError(f'{path}: {exc}') from exc


def read_lines(path):
    path=pathlib.Path(path)
    try:
        lines=path.read_text(encoding='utf-8').splitlines()
        # Reuse the strict decoder without temporary files.
        rows=[]
        for line in lines:
            if not line:raise AnalysisError('empty JSONL record: '+str(path))
            row=json.loads(line,object_pairs_hook=unique_pairs,
                parse_constant=lambda x:(_ for _ in ()).throw(AnalysisError('nonfinite JSONL')))
            if not isinstance(row,dict):raise AnalysisError('non-object JSONL: '+str(path))
            rows.append(row)
        return rows
    except (OSError,ValueError,UnicodeError) as exc:raise AnalysisError(f'{path}: {exc}') from exc


def exports(directory,kind,phase,profile=profiles.STRICT):
    """Decode original bytes and require exact metadata/decoded-copy agreement."""
    directory=pathlib.Path(directory)
    paths=sorted(directory.glob(kind+'-*.bin'))
    if not paths:raise AnalysisError('missing raw export: '+kind)
    rows=[];total=None;finished=False
    size=struct.calcsize(wire.FORMATS[kind])
    for path in paths:
        if finished:raise AnalysisError('extra chunk after export done: '+str(path))
        saved=read_json(path.with_suffix('.json'));meta=saved['metadata'];data=path.read_bytes()
        if saved['payload_sha256']!=wire.digest(data):raise AnalysisError('raw chunk SHA mismatch: '+str(path))
        if total is None:total=meta['total']
        first=len(rows);count=min(256,total-first)
        expected=dict(**profiles.metadata(profile),schema=1,record_type=kind,phase_id=phase,first=first,count=count,total=total,
                      record_bytes=size,next=first+count,done=first+count==total)
        if not profiles.matches(meta,profile):raise IdentityError('raw export measurement profile mismatch')
        if (type(total) is not int or total<0 or meta!=expected or
            path.name!=f'{kind}-{first:06d}.bin' or len(data)!=count*size):
            raise AnalysisError('invalid export metadata/length/order: '+str(path))
        chunk=wire.decode_records(kind,data)
        for i,row in enumerate(chunk):
            if kind=='config':
                if row['rail']!=first+i:raise AnalysisError('config rail order')
            elif row['seq']!=first+i or row['phase']!=phase:
                raise AnalysisError('record sequence/phase mismatch: '+str(path))
        rows.extend(chunk);finished=meta['done']
    if not finished or len(rows)!=total:raise AnalysisError('incomplete export: '+kind)
    if rows!=read_json(directory/(kind+'-records.json')):
        raise AnalysisError('decoded copy differs from raw binary: '+kind)
    return rows


def integrate_rail(rows,t0,t1,hz,excluded=False,profile=profiles.DIAGNOSTIC):
    """Trapezoids only between adjacent valid records; never bridge bad data.

    Subtract the integer window origin before float conversion to retain timing
    precision for large common-counter values. Raw intervals remain in exports.
    """
    if type(hz) is not int or hz<=0 or t1<=t0:raise AnalysisError('invalid integration clock/window')
    duration=(t1-t0)/hz;reasons=[];points=[];updates=[];read_widths=[]
    for r in rows:
        begin=r['begin'][3];end=r['end'][3]
        if type(begin) is not int or type(end) is not int:raise AnalysisError('noninteger board tick')
        x=(begin+end-2*t0)/(2*hz)
        ordered=collect.register_order_valid(r)
        valid=(r['flags']&1 and not r['flags']&~3 and ordered and end>=begin and
               r['power_uW']!=-(2**63) and r['power_uW']>=0)
        if excluded:valid=ordered and profiles.raw_power_ok(r,profile)
        if not valid:reasons.append('invalid sample interrupts interpolation')
        if not ordered:reasons.append('invalid register observation order')
        points.append((x,None if excluded else r['power_uW']/1e6,valid))
        read_widths.append((end-begin)/hz)
        # ADC update evidence is independent of whether signed power is usable.
        if (ordered and r['flags']&2 and not r['flags']&(4|64|128|512) and r.get('mask',8)&8):
            updates.append(x)
    monotonic=all(b[0]>a[0] for a,b in zip(points,points[1:]))
    if not monotonic:reasons.append('nonmonotonic Power read times')
    if not points or points[0][0]>0 or points[-1][0]<duration:
        reasons.append('unbracketed integration boundary')
    # A CVRF observation only says >=1 update occurred; do not count independent conversions.
    if (not updates or updates[0]>0 or updates[-1]<duration or
        any(b-a>.150000000001 for a,b in zip(updates,updates[1:]) if b>0 and a<duration)):
        reasons.append('CVRF observation freshness gap')
    partial=0.;coverage=0.;gaps=[]
    for a,b in zip(points,points[1:]):
        x0,p0,ok0=a;x1,p1,ok1=b
        lo=max(0.,x0);hi=min(duration,x1)
        if hi<=lo:continue
        gap=x1-x0
        if gap>.150000000001:
            reasons.append('Power read gap exceeds 150 ms');gaps.append(gap)
        if not monotonic or not ok0 or not ok1 or gap<=0 or gap>.150000000001:continue
        coverage+=hi-lo
        if not excluded:
            left=p0+(p1-p0)*(lo-x0)/gap;right=p0+(p1-p0)*(hi-x0)/gap
            partial+=(left+right)*(hi-lo)/2
    if abs(coverage-duration)>1e-8:reasons.append('incomplete valid temporal coverage')
    reasons=list(dict.fromkeys(reasons));valid=not reasons
    periods=[b[0]-a[0] for a,b in zip(points,points[1:])]
    scans=list(dict.fromkeys(r['scan_start'] for r in rows))
    return dict(valid=valid,invalid_reasons=reasons,energy_J=partial if valid and not excluded else None,
        mean_W=partial/duration if valid and not excluded else None,partial_energy_J=None if excluded else partial,
        partial_coverage_seconds=coverage,coverage_fraction=coverage/duration,
        records=len(rows),observed_CVRF=len(updates),held_reads=sum(not r['flags']&2 for r in rows),
        max_gap_seconds=max(periods,default=None),read_interval_seconds=dict(
            minimum=min(read_widths,default=None),maximum=max(read_widths,default=None)),
        actual_scan_period_seconds=dict(minimum=min([(b-a)/hz for a,b in zip(scans,scans[1:])],default=None),
            maximum=max([(b-a)/hz for a,b in zip(scans,scans[1:])],default=None)),
        first_power_read_interval_ticks=[rows[0]['begin'][3],rows[0]['end'][3]] if rows else None,
        last_power_read_interval_ticks=[rows[-1]['begin'][3],rows[-1]['end'][3]] if rows else None)


def host_accounting(directory,p,input_sha256=None):
    counts=read_json(directory/'host-counts.json');logs=read_lines(directory/'frame-events.jsonl')
    frames={};missed=[];request_ids=set();reasons=[];e2e=[]
    for e in logs:
        kind=e['event']
        if kind=='missed_slots':
            if type(e['count']) is not int or e['count']<=0:raise AnalysisError('invalid missed slot record')
            if e.get('phase')!=p['name']:reasons.append('missed-slot phase mismatch')
            missed.append(e);continue
        if kind not in ('produced','submitted','evicted','completed','failed'):
            raise AnalysisError('unknown host frame event')
        key=(e['stream'],e['sequence'])
        if e['phase']!=p['name']:reasons.append('host accounting phase mismatch')
        if kind=='produced':
            if key in frames:reasons.append('host accounting duplicate produced frame')
            if input_sha256 and e.get('input_sha256')!=input_sha256:reasons.append('host input identity mismatch')
            frames[key]=dict(e,state='queued')
            continue
        if key not in frames:reasons.append('host accounting event without production');continue
        f=frames[key]
        if kind=='submitted':
            if f['state']!='queued' or e['request_id'] in request_ids:reasons.append('host accounting duplicate submission')
            request_ids.add(e['request_id']);f.update(e,state='submitted')
        elif kind=='evicted':
            if f['state']!='queued':reasons.append('host accounting invalid eviction')
            f['state']='evicted'
        else:
            if f['state']!='submitted':reasons.append('host accounting completion without submission')
            if e['request_id']!=f['request_id']:reasons.append('host accounting response request mismatch')
            if (e['received_monotonic']<f['submitted_monotonic'] or
                f['submitted_monotonic']<f['produced_monotonic']):reasons.append('host clock moved backwards')
            if kind=='completed' and e.get('verified') is not True:reasons.append('host output verification failed')
            if kind=='completed':
                try:wire.validate_business_metadata(e.get('board_response'),{1:'replay_full',2:'replay_compact'}.get(p['mode']),p['timer_hz'])
                except wire.ProtocolError as exc:reasons.append('host inference/output mismatch: '+str(exc))
            f.update(e,state=kind)
            if kind=='completed':e2e.append(e['received_monotonic']-f['produced_monotonic'])
    states=[f['state'] for f in frames.values()]
    actual=dict(produced=len(frames),submitted=sum('request_id' in f for f in frames.values()),
        completed=states.count('completed'),failed=states.count('failed'),evicted=states.count('evicted'),
        remaining=states.count('queued'),in_flight=states.count('submitted'),missed_slots=sum(e['count'] for e in missed),
        timeouts=sum(f.get('failure_type') in ('TimeoutError','timeout') for f in frames.values()))
    actual['scheduled_slots']=actual['produced']+actual['missed_slots']
    lo,hi=p['host_window_monotonic']
    if hi<=lo:raise AnalysisError('invalid host window')
    actual['window_evicted']=sum(f['state']=='evicted' and lo<=f['produced_monotonic']<hi for f in frames.values())
    actual['window_missed_slots']=0
    for e in missed:
        if not p['fps']:raise AnalysisError('missed scheduled slot in unscheduled load')
        if 'schedule_start_monotonic' not in e:
            # Schema-1 journals prior to explicit schedule-origin logging contain the next issued slot.
            next_slot=e['first_sequence']+e['count']
            following=frames.get((e['stream'],next_slot))
            if not following or following.get('planned_monotonic') is None:
                raise AnalysisError('missing schedule origin for missed slots')
            e=dict(e,schedule_start_monotonic=following['planned_monotonic']-next_slot/p['fps'])
        actual['window_missed_slots']+=load.missed_in_window(e,p['fps'],(lo,hi))
    completed=[f for f in frames.values() if f['state']=='completed']
    actual.update(completed_window=sum(lo<=f['received_monotonic']<hi for f in completed),
        completed_drain=sum(f['received_monotonic']>=hi for f in completed),
        completed_pre_window=sum(f['received_monotonic']<lo for f in completed))
    actual['host_fps']=actual['completed_window']/(hi-lo)
    mandatory=('produced','submitted','completed','failed','evicted','remaining','in_flight','missed_slots')
    if any(k not in counts for k in mandatory):reasons.append('host accounting required counts absent')
    for key,value in actual.items():
        if key in counts and (not isinstance(counts[key],(int,float)) or abs(counts[key]-value)>1e-9):
            reasons.append('host accounting mismatch: '+key)
    if not counts.get('conserved') or actual['failed'] or actual['in_flight']:
        reasons.append('host accounting failure/incomplete transaction')
    actual.update(recorded=counts,window_monotonic=[lo,hi],
        submitted_request_ids=sorted(request_ids),
        e2e_seconds_mean=statistics.mean(e2e) if e2e else None,e2e_seconds_max=max(e2e,default=None),
        scope='host monotonic only; independent response receipt window')
    return actual,reasons


def evaluate_phase(directory,synthetic=False,input_sha256=None,profile=profiles.STRICT):
    directory=pathlib.Path(directory);p=read_json(directory/'phase.json')
    s=read_json(directory/'end-status.json');phase=p['board_phase_id']
    policy=profiles.metadata(profile)
    if not profiles.matches(p,profile):raise IdentityError('phase measurement profile mismatch')
    warm=read_json(directory/'warmup-temperatures.json');start=read_json(directory/'start-status.json')
    observed=[r['status'] for r in read_lines(directory/'phase-status.jsonl')]
    snapshots=(warm,start,p['arm_status'],observed)
    for status in [*warm,start,p['arm_status'],*observed,s]:
        if not profiles.matches(status,profile) or status.get('sampler_profile_rails')!=policy['included_count']:
            raise IdentityError('persisted status measurement profile mismatch')
    raw={kind:exports(directory/'exports',kind,phase,profile) for kind in ('config','rails','events','temperatures')}
    reasons=[]
    try:assessment=collect.assess_coverage(directory,p,s,profile,raw,snapshots)
    except collect.IdentityError as exc:raise IdentityError(str(exc)) from exc
    except (collect.GateError,KeyError,TypeError,ValueError) as exc:
        assessment={};reasons.append(str(exc))
    hz=s['timer_hz'];t0=s['t0'];t1=s['t1'];mode=p['mode']
    if hz<=0 or t1<=t0:raise AnalysisError('invalid board phase window')
    if (p['board_t0']!=t0 or p['board_t1']!=t1 or p['timer_hz']!=hz or
        p['arm_status']['t0']!=t0 or p['arm_status']['t1']!=t1 or
        p['arm_status']['timer_hz']!=hz or p['arm_status']['phase_id']!=phase or
        s['sampler_phase']!=phase or s['phase_id']!=phase):reasons.append('phase/window/frequency inconsistency')
    for kind,key in [('rails','rail_records'),('events','event_records'),('temperatures','temperature_records')]:
        if s[key]!=len(raw[kind]):reasons.append('published '+kind+' count mismatch')
    for r in raw['rails']:
        if r['rail'] not in range(18):reasons.append('unexpected rail identity');continue
        if (r['config']!=0x4527 or r['calibration']!=2048):reasons.append('sample sensor configuration mismatch')
        if any(e<b for b,e in zip(r['begin'],r['end'])):reasons.append('backwards register read interval')
        if (r['flags']&1 and r['power_uW']!=r['power']*(31250 if r['rail']==10 else 12500)):
            reasons.append('raw Power-register conversion mismatch')
        if bool(r['flags']&2)!=bool(r['mask']&8):reasons.append('CVRF flag/mask inconsistency')
        if r['flags']&1 and r['end'][4]>min(r['begin'][:4]):
            reasons.append('CVRF observation occurs after payload')
        if (r['flags']&1 and (r['mask']&4 or r['shunt']>=32768 or r['current']>=32768 or
            r['shunt'] in (32767,32768) or r['current'] in (32767,32768) or
            r['bus']==65535 or r['power']==65535)):reasons.append('invalid overflow/saturation/signed sensor data')
    rails=[];power_reasons=[]
    for rail in range(18):
        rows=[r for r in raw['rails'] if r['rail']==rail]
        excluded=rail in policy['excluded_rails']
        r=integrate_rail(rows,t0,t1,hz,excluded,profile);r.update(**policy,included=not excluded,rail=rail,group='PS' if rail<10 else 'PL',
            Power_LSB_W=.03125 if rail==10 else .0125)
        rails.append(r)
        power_reasons.extend(f'rail{rail}: {why}' for why in r['invalid_reasons'])
    events=raw['events']
    # CLOCK reports an earlier sampler observation; START/END have scheduled
    # ticks and can be published after an actual-time event. Publication order
    # is seq; compare timestamps only within their own event families.
    for typ in (5,6,10):
        family=[e for e in events if e['type']==typ]
        if any(b['tick']<a['tick'] for a,b in zip(family,family[1:])):
            reasons.append('nonmonotonic board event family '+str(typ))
    for typ in (1,2,3,4):
        selected=[e for e in events if e['type']==typ]
        if len(selected)!=1:reasons.append('missing/duplicate phase event '+str(typ));continue
        e=selected[0]
        if (typ==1 and (e['begin']!=t0 or e['end']!=t1 or e['mode']!=mode or t0-e['tick']!=hz+hz//4) or
            typ==2 and e['tick']!=t0 or typ==3 and e['tick']!=t1 or
            typ==4 and (e['tick']<t1+hz or e['flags'])):reasons.append('phase marker inconsistency')
    ids=set();clock_sequences=set()
    for e in events:
        if e['type'] not in range(1,12) or e['reserved']:reasons.append('unknown/malformed board event')
        if e['type'] in (7,8,9) or e['mismatch_count']:reasons.append('inference/input/output/fault event')
        if e['type']==10:
            if (e['flags']!=1 or not e['begin']<=e['tick']<=e['end'] or
                e['end']-e['begin']>hz/4 or e['aux'] in clock_sequences):
                reasons.append('invalid/duplicate clock observation')
            clock_sequences.add(e['aux'])
        if e['type'] in (5,6):
            if e['flags']!=1 or e['begin']>e['end'] or e['end']>e['tick']:
                reasons.append('invalid business completion/inference interval')
            if e['type']==5:
                if e['request_id']==0 or e['request_id'] in ids:reasons.append('duplicate/invalid ACK request ID')
                ids.add(e['request_id'])
                if e['mode']!=mode or mode not in (1,2):reasons.append('ACK business mode mismatch')
            elif e['mode']!=mode or mode not in (2,3):reasons.append('inference business mode mismatch')
    successful=[e for e in events if e['type']==(6 if mode==3 else 5) and
                e['mode']==mode and e['flags']==1 and e['mismatch_count']==0] if mode else []
    n=sum(t0<=e['tick']<t1 for e in successful)
    expected=s[{0:'completed_full',1:'completed_full',2:'completed_compact',3:'completed_continuous'}[mode]]
    if n!=expected:reasons.append('board completion counter mismatch')
    host,host_reasons=host_accounting(directory,p,input_sha256);reasons.extend(host_reasons)
    if ids-set(host['submitted_request_ids']):reasons.append('board ACK without matching host submission')
    capture_reasons=list(dict.fromkeys(reasons));capture_valid=not capture_reasons
    reasons=list(dict.fromkeys(capture_reasons+power_reasons));valid=not reasons;duration=(t1-t0)/hz
    energy=sum(r['energy_J'] for r in rails if r['included']) if valid else None
    for r in rails:
        r['energy_mJ_per_completed_frame']=1000*r['energy_J']/n if valid and r['included'] and mode and n else None
    if not valid:invalidate_rails(rails,'parent phase failed validation')
    match=re.match(r'r(\d+)-(.+)',p['name'])
    temps=[r['temperature_mC']/1000 for r in raw['temperatures'] if r['flags']==1]
    return dict(**policy,condition=match[2] if match else p['name'],repetition=int(match[1]) if match else None,
        phase_name=p['name'],board_phase_id=phase,mode=mode,valid=valid,invalid_reasons=reasons,
        capture_valid=capture_valid,capture_invalid_reasons=capture_reasons,
        power_quality_valid=valid,power_invalid_reasons=list(dict.fromkeys(power_reasons)),
        warmup_thermal_stable=assessment.get('warmup_thermal_stable',False),
        warmup_policy='strict-stability' if profile==profiles.STRICT else 'diagnostic-minimum-30s',
        warmup_elapsed_seconds=p.get('warmup_elapsed_seconds'),
        thermal_qualification=assessment.get('thermal_qualification','not established; invalid capture'),
        measurement_origin='SYNTHETIC_NOT_PHYSICAL' if synthetic else 'PHYSICAL_ORIGIN_REQUIRES_SESSION_VALIDATION',
        units=dict(energy='J',mean_power='W',energy_per_frame='mJ/completed frame',time='s'),
        board_window_ticks=[t0,t1],timer_hz=hz,duration_seconds=duration,energy_J=energy,
        mean_W=energy/duration if valid else None,P17mean_W=energy/duration if valid and profile==profiles.DIAGNOSTIC else None,
        P16mean_W=energy/duration if valid and profile==profiles.DIAGNOSTIC16 else None,
        completed_board=n,dropped_frames=host['window_evicted'],missed_slots=host['window_missed_slots'],
        whole_run_evicted_frames=host['evicted'],whole_run_missed_slots=host['missed_slots'],
        host_window_monotonic=host['window_monotonic'],board_window_dropped_frames=None,
        drop_scope='host monotonic [start,end): evictions by frame production time, missed slots by scheduled deadline',
        board_completed_fps=n/duration if capture_valid else None,
        pre_window_board=sum(e['tick']<t0 for e in successful),drain_board=sum(e['tick']>=t1 for e in successful),
        energy_mJ_per_completed_frame=1000*energy/n if valid and n and mode else None,
        offered_input_fps=4*p['fps'] if p['fps'] else None,
        offer_definition='four independent absolute schedules' if p['fps'] else
                         ('closed-loop application saturation' if mode in (1,2) else 'no network frame offer'),
        host=host,rails=rails,phase_assessment=assessment,nominal_ADC_average_interval_ms=35.2,
        temperature_C=dict(minimum=min(temps,default=None),maximum=max(temps,default=None),
            first=temps[0] if temps else None,last=temps[-1] if temps else None,
            endpoint_drift=temps[-1]-temps[0] if temps else None),
        sensor_config=raw['config'],qualifications=QUALIFICATIONS)


def invalidate_rails(rails,reason):
    for rail in rails:
        rail.update(valid=False,energy_J=None,mean_W=None,energy_mJ_per_completed_frame=None)
        rail['invalid_reasons'].append(reason)


def analyze_phase(directory,synthetic=False,input_sha256=None,profile=profiles.STRICT):
    directory=pathlib.Path(directory)
    result=evaluate_phase(directory,synthetic,input_sha256,profile)
    result['raw_hashes']={collect.relative_key(f,directory):dict(bytes=f.stat().st_size,sha256=collect.file_hash(f))
                          for f in sorted(directory.rglob('*')) if f.is_file()}
    return result


def aggregate(stages):
    groups={}
    for stage in stages:
        if not profiles.matches(stage,stages[0]['measurement_profile']):raise AnalysisError('mixed measurement profiles')
        groups.setdefault(stage['condition'],[]).append(stage)
    result=[]
    for name,values in groups.items():
        row=dict(**profiles.metadata(values[0]['measurement_profile']),condition=name,repetitions_total=len(values),repetitions_valid=sum(s['valid'] for s in values),
            warmup_thermal_stable_repetitions=sum(s['valid'] and s.get('warmup_thermal_stable') is True for s in values),
            thermal_qualification='Warmup qualification only; inspect each phase and measured temperature series before claiming steady state.',
            interpretation='Repeated phases of this setup; not asserted independent restarts or instrument accuracy.')
        for metric in ('mean_W','energy_J','board_completed_fps','energy_mJ_per_completed_frame'):
            data=[s[metric] for s in values if s['valid'] and s.get(metric) is not None]
            row[metric]=dict(n=len(data),mean=statistics.mean(data) if data else None,
                sample_SD=statistics.stdev(data) if len(data)>1 else None)
        result.append(row)
    return result


def analyze_session(path,synthetic=False,acceptance_session=None,profile=profiles.STRICT):
    path=pathlib.Path(path).resolve();session=read_json(path/'session.json')
    recorded=read_json(path/'inventory.json')
    try:
        if collect.normalize_inventory(recorded)!=collect.inventory(path):
            raise AnalysisError('session raw evidence inventory mismatch')
    except collect.GateError as exc:raise AnalysisError(str(exc)) from exc
    info=collect.preflight(ROOT,profile);identity=info['identity'];reasons=[]
    if (not profiles.matches(session,profile) or session.get('schema')!='e07-host-session-v1' or session.get('identity')!=identity or
        read_json(path/'firmware-identity.json')!=identity or session.get('source_hashes')!=collect.source_hashes(ROOT) or
        session.get('manifest')!=info['manifest'] or read_json(path/'manifest.json')!=info['manifest']):
        raise AnalysisError('wrong firmware/source/manifest identity')
    summaries=session.get('phases',[])
    if not isinstance(summaries,list):
        raise IdentityError('malformed phase summary list')
    if session.get('status')=='COMPLETE' and len(summaries)!=len(session['plan']):
        raise IdentityError('complete session phase summary count differs from plan')
    if any(not isinstance(row,dict) or not profiles.matches(row,profile) for row in summaries):
        raise IdentityError('saved phase summary measurement profile mismatch')
    hello=read_json(path/'hello.json')
    expected_hello=wire.expected_greeting(identity)
    try:collect.validate_receipt_value(ROOT,session.get('sd_receipt',{}),profile)
    except collect.GateError as exc:raise AnalysisError('session SD receipt mismatch') from exc
    try:collect.validate_status(read_json(path/'startup-status.json'),profile=profile)
    except collect.GateError as exc:raise AnalysisError('startup status identity/readiness mismatch') from exc
    if hello!=expected_hello:
        raise AnalysisError('wrong board firmware greeting identity')
    if session.get('status')!='COMPLETE':reasons.append('session incomplete')
    binding=session.get('acceptance_binding')
    candidate=None
    if not synthetic and session.get('kind')=='formal' and isinstance(binding,dict):
        if not profiles.matches(binding,profile):raise AnalysisError('acceptance profile binding mismatch')
        candidate=pathlib.Path(acceptance_session or binding['path']).resolve()
        if candidate.is_file() and not profiles.matches(read_json(candidate),profile):
            raise AnalysisError('acceptance dataset measurement profile mismatch')
    if not synthetic:
        if session.get('physical') is not True or session.get('peer_ip')!='192.168.10.2':
            reasons.append('physical-origin session evidence absent')
        try:
            if session['kind']=='acceptance':
                collect.validate_acceptance(path/'session.json',identity,session['board_id'],session['controls'])
            elif session['kind']=='formal':
                if candidate is None or not candidate.is_file():raise AnalysisError('acceptance raw session unavailable; return it alongside formal data')
                actual=collect.validate_acceptance(candidate,identity,session['board_id'],session['controls'])
                if any(actual[k]!=binding[k] for k in ('sha256','inventory_sha256')):
                    raise IdentityError('physical acceptance binding mismatch')
            else:raise AnalysisError('unknown session kind')
        except collect.IdentityError as exc:raise IdentityError(str(exc)) from exc
        except (collect.GateError,KeyError,OSError,AnalysisError) as exc:reasons.append('acceptance gate: '+str(exc))
    stages=[]
    for index,plan in enumerate(session['plan']):
        if not profiles.matches(plan,profile):raise AnalysisError('session plan measurement profile mismatch')
        try:relative=collect.phase_relative_path(session,index,plan)
        except collect.GateError as exc:raise AnalysisError(str(exc)) from exc
        directory=path/relative
        if not (directory/'phase.json').is_file():
            stages.append(dict(**profiles.metadata(profile),condition=plan['name'],repetition=None,phase_name=plan['name'],valid=False,
                invalid_reasons=['missing/incomplete phase evidence'],energy_J=None,mean_W=None,
                board_completed_fps=None,energy_mJ_per_completed_frame=None));continue
        saved=read_json(directory/'phase.json')
        if any(saved.get(k)!=v for k,v in plan.items()):raise AnalysisError('phase differs from session plan')
        stage=analyze_phase(directory,synthetic,identity['artifact_hashes']['input'],profile)
        stage['phase_path']=relative
        if reasons:
            stage['valid']=False;stage['invalid_reasons'].extend(reasons)
            invalidate_rails(stage['rails'],'parent session failed validation')
            stage['capture_valid']=False;stage['power_quality_valid']=False
            for key in ('energy_J','mean_W','P17mean_W','P16mean_W','board_completed_fps','energy_mJ_per_completed_frame'):stage[key]=None
        elif not synthetic:stage['measurement_origin']='PHYSICAL_USER_SESSION'
        stages.append(stage)
    return dict(**profiles.metadata(profile),schema='e07-independent-analysis-v1',measurement_origin='SYNTHETIC_NOT_PHYSICAL' if synthetic else 'USER_SESSION',
        valid=bool(stages) and all(s['valid'] for s in stages),session_invalid_reasons=reasons,
        capture_complete=session.get('status')=='COMPLETE' and bool(stages) and all(s.get('capture_valid') for s in stages),
        firmware_sha256=identity['firmware_sha256'],delivered_candidate_physical_status=identity['physical_status'],
        controls=session.get('controls'),board_id=session.get('board_id'),stages=stages,aggregates=aggregate(stages),
        qualifications=QUALIFICATIONS,analysis_sha256=collect.file_hash(__file__),
        raw_inventory_sha256=collect.file_hash(path/'inventory.json'),session_sha256=collect.file_hash(path/'session.json'))


def write_results(output,result):
    output=pathlib.Path(output);output.mkdir(parents=True,exist_ok=False)
    wire.save_json(output/'analysis.json',result)
    profile_fields=list(profiles.metadata(result['measurement_profile']))
    fields=profile_fields+['condition','repetition','phase_name','valid','invalid_reasons','measurement_origin',
        'duration_seconds','capture_valid','power_quality_valid','warmup_policy','warmup_elapsed_seconds','warmup_thermal_stable','thermal_qualification',
        'drop_scope','host_window_monotonic','dropped_frames','missed_slots',
        'whole_run_evicted_frames','whole_run_missed_slots','board_window_dropped_frames','P17mean_W','P16mean_W','energy_J','mean_W','completed_board','board_completed_fps',
        'energy_mJ_per_completed_frame','offered_input_fps','drain_board']
    with (output/'per-stage.csv').open('x',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fields);writer.writeheader()
        for stage in result['stages']:
            row={k:stage.get(k) for k in fields};row['invalid_reasons']=' | '.join(stage['invalid_reasons']);writer.writerow(row)
    with (output/'per-repeat.csv').open('x',encoding='utf-8-sig',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(profile_fields+['condition','repetitions_total','repetitions_valid','warmup_thermal_stable_repetitions','thermal_qualification','metric','unit','n','mean','sample_SD'])
        for group in result['aggregates']:
            for metric,unit in [('mean_W','W'),('energy_J','J'),('board_completed_fps','frames/s'),
                                ('energy_mJ_per_completed_frame','mJ/completed frame')]:
                m=group[metric];writer.writerow([group[k] for k in profile_fields]+[group['condition'],group['repetitions_total'],group['repetitions_valid'],group['warmup_thermal_stable_repetitions'],group['thermal_qualification'],metric,unit,m['n'],m['mean'],m['sample_SD']])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session',type=pathlib.Path,help='raw session directory')
    parser.add_argument('--output',required=True,type=pathlib.Path,help='new derived-only directory outside the raw session')
    scope=parser.add_mutually_exclusive_group()
    scope.add_argument('--diagnostic17',action='store_true',help='require diagnostic17 session and identity')
    scope.add_argument('--diagnostic16',action='store_true',help='require diagnostic16 session; exclude7/15')
    parser.add_argument('--synthetic',action='store_true',help='label every output SYNTHETIC_NOT_PHYSICAL; cannot qualify acceptance')
    parser.add_argument('--acceptance-session',type=pathlib.Path,help='relocated raw acceptance session.json; exact original hashes still required')
    args=parser.parse_args(argv)
    if sys.version_info<(3,11):raise AnalysisError('Python3.11+ required')
    raw=args.session.resolve();out=args.output.resolve()
    if out.is_relative_to(ROOT.resolve()):raise AnalysisError('derived output must be outside immutable package')
    if out==raw or raw in out.parents:raise AnalysisError('derived output must be outside immutable raw session')
    collect.verify_delivery(ROOT)
    profile=profiles.DIAGNOSTIC16 if args.diagnostic16 else profiles.DIAGNOSTIC if args.diagnostic17 else profiles.STRICT
    result=analyze_session(raw,args.synthetic,args.acceptance_session,profile);write_results(out,result)
    print(json.dumps(dict(**profiles.metadata(profile),status='VALID' if result['valid'] else 'INVALID',output=str(out),measurement_origin=result['measurement_origin'])))
    return 0 if result['valid'] else 1


if __name__=='__main__':
    try:sys.exit(main())
    except (AnalysisError,collect.GateError,wire.ProtocolError,OSError,ValueError,KeyError,TypeError) as exc:
        print('FAILED: '+str(exc),file=sys.stderr);sys.exit(2)
