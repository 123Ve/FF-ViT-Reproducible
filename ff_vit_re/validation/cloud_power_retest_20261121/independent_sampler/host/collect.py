"""Portable collector. Run with Python 3.11+: python host/collect.py --help.

No third-party modules, runtime SD hashing claim, or host/board clock mixing.
Raw export decoding is in wire.decode_records; analysis may consume saved
*-records.json directly, retaining binary chunks as the source evidence.
"""
import argparse
import datetime
import hashlib
import ipaddress
import json
import math
import pathlib
import platform
import socket
import statistics
import sys
import threading
import time
import traceback
sys.dont_write_bytecode=True

if __package__:
    from . import wire, load, profiles
else:
    sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
    from host import wire, load, profiles

ROOT=pathlib.Path(__file__).resolve().parents[1]
COUNTERS=('i2c_errors','invalid_samples','stale_samples','scan_overruns','overflows','temperature_errors')


class GateError(RuntimeError):
    pass


class IdentityError(GateError):
    """Mismatched measurement, source, image, or evidence binding requires hard refusal."""


def require_profile(record,profile,sampler=False):
    if not profiles.matches(record,profile) or (sampler and record.get('sampler_profile_rails')!=profiles.metadata(profile)['included_count']):
        raise IdentityError('measurement profile/compiled sampler mismatch')


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def file_hash(path):
    h=hashlib.sha256()
    with pathlib.Path(path).open('rb') as f:
        while block:=f.read(1024*1024):h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding='utf-8'))


def check_file(path,expected):
    path=pathlib.Path(path)
    if not path.is_file() or path.stat().st_size!=expected['bytes'] or file_hash(path)!=expected['sha256']:
        raise GateError('file missing/size/hash mismatch: '+str(path))


def source_hashes(root=ROOT):
    paths=('host/wire.py','host/profiles.py','host/analyze.py','host/load.py','host/collect.py','Run-PowerRetest.ps1','PROTOCOL.md')
    return {name:file_hash(root/name) for name in paths}


def preflight(root=ROOT,profile=profiles.STRICT):
    root=pathlib.Path(root).resolve()
    identity_name,sums_name,sd=profiles.paths(profile)
    identity=read_json(root/identity_name)
    manifest=read_json(root/sums_name)
    h=wire.digest(canonical(identity['canonical_payload']))
    if (not profiles.matches(identity,profile) or not profiles.matches(identity['canonical_payload'],profile) or
        '-DE07_PROFILE_RAILS='+str(identity['included_count']) not in identity['canonical_payload']['options'] or
        h!=identity['firmware_sha256'] or h!=identity['advertised_sha256'] or
        identity['candidate']!='E07_INDEPENDENT_POWER_V1' or identity['protocol_schema']!=1 or
        identity['artifact_hashes']!=identity['canonical_payload']['artifact_hashes']):
        raise GateError('firmware identity canonical hash/schema mismatch')
    required={sd+'/'+name for name in ('BOOT.BIN','FIRMWARE_IDENTITY.json','input.bin','output.bin','weights.bin')}
    if set(manifest)!=required:raise GateError('unexpected/incomplete SD manifest')
    for name,entry in manifest.items():check_file(root/name,entry)
    if read_json(root/sd/'FIRMWARE_IDENTITY.json')!=identity:
        raise GateError('SD identity differs from package identity')
    if identity['BOOT']!=dict(manifest[sd+'/BOOT.BIN'],path=sd+'/BOOT.BIN'):
        raise GateError('BOOT identity differs from SD manifest')
    for key in ('input','output','weights'):
        if manifest[f'{sd}/{key}.bin']['sha256']!=identity['artifact_hashes'][key]:
            raise GateError('frozen data identity mismatch')
    # ELF locations are bound by the identity. Verify actual delivered ELF files.
    if set(identity['ELF'])!={'service','sampler'}:raise GateError('missing expected CPUs')
    for core,entry in identity['ELF'].items():
        if entry['path']!=identity['build_directory']+'/'+core+'.elf' or not (root/entry['path']).resolve().is_relative_to(root):
            raise GateError('ELF path does not match build')
        check_file(root/entry['path'],entry)
        if h.encode() not in (root/entry['path']).read_bytes():raise GateError('ELF does not embed firmware identity')
    for name,expected in identity['canonical_payload']['sources'].items():
        if not (root/name).resolve().is_relative_to(root) or file_hash(root/name)!=expected:
            raise GateError('firmware source hash mismatch: '+name)
    return dict(identity=identity,manifest=manifest,manifest_sha256=file_hash(root/sums_name),
                identity_sha256=file_hash(root/identity_name))


def verify_sd(root,sd_root,receipt_path,profile=profiles.STRICT):
    info=preflight(root,profile)
    sd_root=pathlib.Path(sd_root).resolve()
    for name,expected in info['manifest'].items():check_file(sd_root/pathlib.Path(name).name,expected)
    if read_json(sd_root/'FIRMWARE_IDENTITY.json')!=info['identity']:
        raise GateError('copied SD firmware identity mismatch')
    receipt=dict(**profiles.metadata(profile),schema='e07-sd-copy-verification-v1',tool='host/collect.py',verified_utc=utcnow(),
        sd_root=str(sd_root),firmware_sha256=info['identity']['firmware_sha256'],
        identity_sha256=info['identity_sha256'],manifest_sha256=info['manifest_sha256'],
        files=info['manifest'],source_hashes=source_hashes(pathlib.Path(root)),
        assumption='The verified physical card is unchanged between verification and board use; firmware does not hash SD at runtime.')
    receipt['receipt_sha256']=wire.digest(canonical(receipt))
    wire.save_json(receipt_path,receipt)
    return receipt


def validate_receipt(root,path,profile=profiles.STRICT):
    return validate_receipt_value(root,read_json(path),profile)


def validate_receipt_value(root,value,profile):
    info=preflight(root,profile)
    unsigned={k:v for k,v in value.items() if k!='receipt_sha256'}
    if (not profiles.matches(value,profile) or value.get('schema')!='e07-sd-copy-verification-v1' or value.get('tool')!='host/collect.py' or
        value.get('receipt_sha256')!=wire.digest(canonical(unsigned)) or
        value.get('files')!=info['manifest'] or value.get('firmware_sha256')!=info['identity']['firmware_sha256'] or
        value.get('identity_sha256')!=info['identity_sha256'] or
        value.get('manifest_sha256')!=info['manifest_sha256'] or
        value.get('source_hashes')!=source_hashes(pathlib.Path(root)) or
        not value.get('sd_root') or not value.get('assumption')):
        raise IdentityError('missing/mismatching tool-generated SD copy-verification receipt')
    try:datetime.datetime.fromisoformat(value['verified_utc'])
    except (KeyError,ValueError):raise GateError('receipt lacks valid verification time')
    return value


def physical_peer(address):
    ip=ipaddress.ip_address(address)
    return not (ip.is_loopback or ip.is_unspecified or ip.is_multicast)


def temperature_sample_valid(s):
    """Sensor health/freshness is required even without a steady-state claim."""
    try:
        hz=s['timer_hz']
        return (hz>0 and s['temperature_valid']==1 and
                0<=s['now_ticks']-s['temperature_tick']<=2*hz and
                -55000<=s['temperature_mC']<=150000)
    except (KeyError,TypeError):return False


def validate_status(s,require_ready=True,profile=profiles.STRICT):
    require_profile(s,profile,sampler=True)
    try:
        hz=s['timer_hz'];now=s['now_ticks']
        checks=(s['schema']==1,s['snapshot_valid'] is True,s['service_core']==0,s['sampler_core']==1,
            hz>0,hz==s['sampler_hz'],s['epoch']==s['sampler_epoch'],s['configured_mask']==262143,
            profiles.qualified(s,profile),
            s['clock_checks']>=3,s['heartbeat_advances']>=3,
            0<=now-s['sampler_heartbeat']<=hz/4,now-s['configured_tick']>=hz,
            temperature_sample_valid(s),
            s['faults']==0,s['sampler_faults']==0,not any(s[k] for k in COUNTERS),s['sampling_enabled']==1,
            not require_ready or s['ready'] is True)
        if not all(checks):raise GateError('sampler readiness/clock/configuration/fault gate failed')
    except (KeyError,TypeError):raise GateError('incomplete/malformed power_status')


def validate_config(rows):
    if len(rows)!=18 or {r['rail'] for r in rows}!=set(range(18)):
        raise GateError('configuration missing rails')
    for row in rows:
        if (row['flags']!=1 or row['manufacturer']!=0x5449 or row['die']&0xfff0!=0x2260 or
            row['config']!=0x4527 or row['calibration']!=2048 or row['end']<row['begin']):
            raise GateError('INA226 configuration readback invalid')


def validate_condition(status,plan,sampling_enabled=1):
    """Compare reported selected controls to the requested condition.

    These fields are service control echoes; sampler operation is separately
    observed through readiness, advancing heartbeats, scans and exported data.
    """
    require_profile(status,plan.get('measurement_profile',profiles.STRICT),sampler=True)
    expected={key:plan[key] for key in ('mode','scan_ms','offset_ms')}
    expected['sampling_enabled']=sampling_enabled
    for key,wanted in expected.items():
        if type(status.get(key)) is not int or status[key]!=wanted:
            raise GateError(f'condition mismatch: {key}: requested {wanted}, reported {status.get(key)}')


def wait_sampling_observed(client,setting,enabled,directory,timeout=5):
    """Infer off from stable scans; on additionally requires ready and progress.

    Protocol schema1 exposes the service enabled control, not the sampler's
    private enabled echo. Record behavior rather than naming it a direct ACK.
    """
    log=Journal(pathlib.Path(directory)/f'sampling{enabled}-observations.jsonl')
    deadline=time.monotonic()+timeout
    previous=None;stable_tick=None;stable_host=None
    baseline={k:setting[k] for k in COUNTERS}
    try:
        while time.monotonic()<deadline:
            s=client.status();host_now=time.monotonic()
            log(dict(host_monotonic=host_now,status=s))
            hz=s['timer_hz'];heartbeat=s['sampler_heartbeat']
            if (not profiles.qualified(s,client.profile) or not s['snapshot_valid'] or hz<=0 or s['sampler_hz']!=hz or
                s['faults'] or s['sampler_faults'] or s['scan_overruns'] or
                any(s[k]!=baseline[k] for k in COUNTERS) or
                not 0<=s['now_ticks']-heartbeat<=hz/4):
                raise GateError('sampler toggle observation unhealthy/stale/error counters changed')
            validate_condition(s,setting,sampling_enabled=enabled)
            if previous and heartbeat<=previous['sampler_heartbeat']:
                raise GateError('sampler toggle heartbeat stalled/backward')
            fresh=heartbeat>setting['now_ticks']
            if fresh and s['sampling_enabled']==enabled:
                if enabled and s['ready'] is True and s['scan_count']>setting['scan_count']:
                    return s
                if not enabled:
                    if previous and s['scan_count']==previous['scan_count'] and stable_tick is not None:
                        # Two periods of the slowest allowed scan, checked in
                        # both clocks independently. Never subtract the clocks.
                        if heartbeat-stable_tick>=.046*hz and host_now-stable_host>=.046:
                            return s
                    else:stable_tick=heartbeat;stable_host=host_now
            else:stable_tick=None;stable_host=None
            previous=s
            time.sleep(.025)
        raise GateError('sampler toggle observation deadline expired')
    finally:log.close()


def diagnostics(client,path):
    path=pathlib.Path(path)/'diagnostics'
    path.mkdir(parents=True,exist_ok=True)
    for name,call in [('status',client.status),
                      ('config',lambda:client.export('config',path)),
                      ('latest',lambda:client.export('latest',path))]:
        try:
            value=call()
            if name=='status':wire.save_json(path/'status.json',value)
            elif name=='latest':
                # Derived explanation only; original binary/registers remain untouched.
                signed=lambda x:x-65536 if x&32768 else x
                names={4:'I2C_ERROR',8:'OVERFLOW',16:'SATURATED',32:'STALE',
                       64:'CONFIG_ERROR',128:'CLOCK_ERROR',256:'NEGATIVE',512:'NOT_READY'}
                wire.save_json(path/'fault-summary.json',dict(
                    **profiles.metadata(client.profile),
                    scan_provenance='cached complete scan; live or frozen status not attested; not a power result or calibration',
                    negative_policy='Raw NEGATIVE retained; diagnostic capture and included-power quality are separate; no clipping or offset correction.',
                    rails=[dict(rail=r['rail'],scan=r['scan'],flags=r['flags'],
                        reasons=[label for bit,label in names.items() if r['flags']&bit],
                        shunt_raw=r['shunt'],shunt_signed=signed(r['shunt']),
                        shunt_uV=2.5*signed(r['shunt']),current_raw=r['current'],
                        current_signed=signed(r['current']),power_raw=r['power'],
                        power_uW=r['power_uW'],mask_raw=r['mask'],
                        read_begin=r['begin'],read_end=r['end']) for r in value]))
        except Exception as exc:
            wire.save_json(path/(name+'-error.json'),dict(type=type(exc).__name__,detail=str(exc)))


def ensure_ready(client,path,timeout=5):
    """Allow ordinary initialization, then require three healthy advances.

    A coherent all-zero sampler publication may precede CPU1 initialization.
    Published wrong identity, sensor faults or error counters are never retried.
    """
    log=Journal(pathlib.Path(path)/'readiness-observations.jsonl')
    deadline=time.monotonic()+timeout;previous=None;healthy=0
    original_timeout=client.sock.gettimeout()
    try:
        while time.monotonic()<deadline:
            remaining=deadline-time.monotonic()
            client.sock.settimeout(min(original_timeout or remaining,remaining))
            s=client.status();log(dict(host_monotonic=time.monotonic(),status=s))
            unpublished=(s['sampler_hz']==s['sampler_epoch']==s['configured_mask']==s['sampler_heartbeat']==0)
            if (s['schema']!=1 or s['physical_status']!='NOT_RUN' or s['service_core']!=0 or s['timer_hz']<=0 or
                s['faults'] or s['sampler_faults'] or any(s[k] for k in COUNTERS) or s['sampling_enabled']!=1 or
                not 0<=s['configured_mask']<=262143 or s['sampler_core'] not in (0,1) or
                not unpublished and (s.get('sampler_profile_rails')!=profiles.metadata(client.profile)['included_count'] or s['sampler_core']!=1 or s['sampler_hz']!=s['timer_hz'] or s['sampler_epoch']!=s['epoch'])):
                raise GateError('fatal readiness identity/configuration/sensor fault')
            if s['ready'] is True:
                validate_status(s,profile=client.profile)
                if previous and (s['sampler_heartbeat']<=previous['sampler_heartbeat'] or
                                 s['now_ticks']<=previous['now_ticks']):
                    raise GateError('heartbeat/service clock did not advance')
                previous=s;healthy+=1
                if healthy==3:return s
            else:previous=None;healthy=0
            time.sleep(min(.1,max(0,deadline-time.monotonic())))
        raise GateError('startup readiness deadline expired')
    except Exception:
        diagnostics(client,path)
        raise
    finally:
        client.sock.settimeout(original_timeout);log.close()


def thermal_stable(samples):
    if not samples:return False
    unique={}
    for s in samples:
        try:
            hz=s['timer_hz'];tick=s['temperature_tick']
            if not temperature_sample_valid(s):return False
            unique[tick]=s
        except (KeyError,TypeError):return False
    latest=max(unique)
    hz=unique[latest]['timer_hz']
    window=[unique[t] for t in sorted(unique) if t>=latest-30*hz]
    ticks=[s['temperature_tick'] for s in window]
    if len(window)<30 or ticks[-1]-ticks[0]<29*hz:return False
    if any(b<=a or b-a>1.5*hz for a,b in zip(ticks,ticks[1:])):return False
    values=[s['temperature_mC'] for s in window]
    first=[s['temperature_mC'] for s in window if s['temperature_tick']<ticks[0]+10*hz]
    last=[s['temperature_mC'] for s in window if s['temperature_tick']>ticks[-1]-10*hz]
    return (len(first)>=9 and len(last)>=9 and max(values)-min(values)<=1000 and
            abs(statistics.mean(first)-statistics.mean(last))<=200)


def warmup_ready(profile,elapsed,samples):
    """Fixed diagnostic warmup; strict18 still needs the original stable window."""
    profiles.metadata(profile)
    if type(elapsed) not in (int,float) or not math.isfinite(elapsed) or elapsed<30 or not samples:return False
    if profile==profiles.STRICT:return thermal_stable(samples)
    try:
        hz=samples[-1]['timer_hz'];ticks=[s['now_ticks'] for s in samples]
        return (len(ticks)>=2 and ticks[-1]-ticks[0]>=29*hz and
                all(b>a for a,b in zip(ticks,ticks[1:])) and
                all(temperature_sample_valid(s) and s['timer_hz']==hz for s in samples))
    except (KeyError,TypeError):return False


def board_counts(events,s,mode):
    typ=6 if mode==3 else 5
    valid=[e for e in events if e['type']==typ and e['mode']==mode and e['flags']==1 and e['mismatch_count']==0]
    n=sum(s['t0']<=e['tick']<s['t1'] for e in valid)
    expected=s[{0:'completed_full',1:'completed_full',2:'completed_compact',3:'completed_continuous'}[mode]]
    if mode and n!=expected:raise GateError('board counter differs from actual ACK/inference completion events')
    return dict(completed_board=n,drain_board=sum(e['tick']>=s['t1'] for e in valid))


def register_order_valid(row):
    """Schema1 stores Mask last but the repaired firmware reads it first."""
    begin,end=row['begin'],row['end']
    order=(4,0,1,2,3)
    return (len(begin)==len(end)==5 and all(e>=b for b,e in zip(begin,end)) and
            all(end[a]<=begin[b] for a,b in zip(order,order[1:])))


def assess_phase(directory,profile=profiles.STRICT,input_sha256=None):
    """Authorization and offline analysis use the same full phase evaluation."""
    from host import analyze
    try:result=analyze.evaluate_phase(directory,False,input_sha256,profile)
    except IdentityError:raise
    except (analyze.AnalysisError,KeyError,TypeError,ValueError) as exc:raise GateError(str(exc)) from exc
    acceptable=result['valid'] if profile==profiles.STRICT else result['capture_valid']
    if not acceptable:raise GateError('invalid phase evidence: '+' | '.join(result['invalid_reasons']))
    return dict(result['phase_assessment'],capture_valid=result['capture_valid'],
                power_quality_valid=result['valid'],power_invalid_reasons=result['power_invalid_reasons'])


def assess_coverage(directory,p,s,profile,raw,snapshots):
    """Validate physical coverage, clock and sampler health before interpreting energy."""
    rails,events,temps=raw['rails'],raw['events'],raw['temperatures']
    validate_config(raw['config'])
    if any(r['rail']!=i%18 or r['scan']!=rails[0]['scan']+i//18 or
           r['scan_start']!=rails[i-i%18]['scan_start'] for i,r in enumerate(rails)) or len(rails)%18:
        raise GateError('missing, extra or disordered physical rail')
    if [r for r in rails if r['rail']==7]!=read_json(directory/'exports/rail7-records.json'):
        raise GateError('Rail7 decoded subset differs from raw export')
    if [r for r in rails if r['rail']==15]!=read_json(directory/'exports/rail15-records.json'):
        raise GateError('Rail15 decoded subset differs from raw export')
    if s['faults'] or s['sampler_faults']:raise GateError('phase/latched sampler fault')
    if s['state']!=4 or s['sampler_state']!=4:raise GateError('phase not frozen DONE')
    if s['t0']>=s['t1'] or s['timer_hz']<=0:raise GateError('bad board measurement window')
    if (s['t1']-s['t0'])!=p['seconds']*s['timer_hz']:raise GateError('board window duration mismatch')
    if s['phase_id']!=p['board_phase_id']:raise GateError('board phase identity mismatch')
    warm,start,arm,observed=snapshots
    if not observed:raise GateError('missing measured-phase configuration observations')
    counters=[];included_counters=[]
    for status in [*warm,start,arm,*observed,s]:
        validate_condition(status,p)
        validate_status(status,require_ready=False,profile=profile)
        if (status['timer_hz'],status['epoch'])!=(s['timer_hz'],s['epoch']):
            raise GateError('phase clock/boot epoch changed')
        counters.append(status['excluded_negative_samples'])
        included_counters.append(status['included_negative_samples'])
    excluded=profiles.metadata(profile)['excluded_rails']
    warnings=sum(r['rail'] in excluded and r['flags'] in (256,258) for r in rails)
    included_warnings=sum(r['rail'] not in excluded and r['flags'] in (256,258) for r in rails)
    if (any(b<a for a,b in zip(counters,counters[1:])) or
        s['excluded_negative_samples']-start['excluded_negative_samples']<warnings):
        raise GateError('excluded-negative counter rolled back or missed exported warnings')
    if (any(b<a for a,b in zip(included_counters,included_counters[1:])) or
        s['included_negative_samples']-start['included_negative_samples']<included_warnings):
        raise GateError('included-negative counter rolled back or missed exported warnings')
    steady=thermal_stable(warm)
    elapsed=p.get('warmup_elapsed_seconds')
    if profile==profiles.STRICT:
        if not steady:raise GateError('warmup thermal evidence failed')
    elif not warmup_ready(profile,elapsed,warm):
        raise GateError('diagnostic minimum warmup/temperature evidence failed')
    hz=s['timer_hz'];coverage=[];overlap=0
    intervals=sorted((e['begin'],e['end']) for e in events if e['type']==6 and e['flags']==1)
    for rail in range(18):
        rows=[r for r in rails if r['rail']==rail]
        if any(not profiles.raw_capture_ok(r,profile) or not register_order_valid(r) for r in rows):
            raise GateError('invalid raw rail power, flags, or register read order')
        ticks=[(r['begin'][3]+r['end'][3])/2 for r in rows]
        # The sampler stops scheduling at the postguard deadline. The final
        # scan can precede that deadline by one scan period; require boundary
        # bracketing plus actual guard data, not an impossible final exact tick.
        if (not ticks or ticks[0]>s['t0']-hz or ticks[-1]<s['t1'] or
            any(b<=a or b-a>.15*hz for a,b in zip(ticks,ticks[1:]))):
            raise GateError('rail coverage/guards/freshness gap')
        updates=[t for t,r in zip(ticks,rows) if r['flags']&2]
        if not updates or updates[0]>s['t0'] or updates[-1]<s['t1'] or any(b-a>.15*hz for a,b in zip(updates,updates[1:])):
            raise GateError('CVRF observation freshness gap')
        if any(any(a<r['end'][3] and b>r['begin'][3] for a,b in intervals) for r in rows):overlap+=1
        coverage.append(dict(rail=rail,first_power_tick=ticks[0],last_power_tick=ticks[-1],
                             records=len(rows),observed_CVRF=len(updates)))
    if not temps or any(t['flags']!=1 or t['raw'] in (0,65535) or
                       not -55000<=t['temperature_mC']<=150000 for t in temps):
        raise GateError('missing/invalid temperature log')
    temp_ticks=[t['tick'] for t in temps]
    if (temp_ticks[0]>s['t0'] or temp_ticks[-1]<s['t1']-hz or
        any(b<=a or b-a>2*hz for a,b in zip(temp_ticks,temp_ticks[1:]))):
        raise GateError('phase temperature coverage/freshness gap')
    c=board_counts(events,s,p['mode'])
    if p['mode'] in (2,3) and (not intervals or overlap!=18):
        raise GateError('missing inference/read interval overlap evidence')
    counts=read_json(directory/'host-counts.json')
    if not counts.get('conserved') or counts.get('failed',0) or counts.get('in_flight',0):
        raise GateError('host frame failure/accounting loss')
    return dict(**profiles.metadata(profile),exported_excluded_negative_rows=warnings,
                exported_included_negative_rows=included_warnings,
                warmup_thermal_stable=steady,warmup_elapsed_seconds=elapsed,
                warmup_policy='strict-stability' if profile==profiles.STRICT else 'diagnostic-minimum-30s',
                thermal_qualification='warmup criterion met; measured temperatures retained separately' if steady else
                    ('not established; strict18 rejected' if profile==profiles.STRICT else 'not established; diagnostic time-window average'),
                prearm_to_end_excluded_negative_delta=s['excluded_negative_samples']-start['excluded_negative_samples'],coverage=coverage,inference_read_overlap_rails=overlap,**c,
                metrology_claim='Read/inference overlap is timing evidence only; ADC windows, bias and absolute accuracy remain unqualified.')


def acceptance_plan(profile=profiles.STRICT):
    plan=[dict(name='startup-idle',mode=0,fps=None,seconds=10,scan_ms=20,offset_ms=0),
          dict(name='startup-full40',mode=1,fps=10,seconds=10,scan_ms=20,offset_ms=0),
          dict(name='startup-compact120',mode=2,fps=30,seconds=10,scan_ms=20,offset_ms=0),
          dict(name='startup-continuous',mode=3,fps=None,seconds=10,scan_ms=20,offset_ms=0)]
    for scan in (17,23):
        for offset in (0,scan//2):
            for mode in (2,3):
                plan.append(dict(name=f'scan{scan}-offset{offset}-mode{mode}',mode=mode,
                    fps=30 if mode==2 else None,seconds=60,scan_ms=scan,offset_ms=offset))
    return [dict(p,**profiles.metadata(profile)) for p in plan]


def formal_plan(seconds=120,repetitions=5,profile=profiles.STRICT):
    plan=[]
    for repetition in range(repetitions):
        plan.append(dict(name=f'r{repetition+1}-Idle',mode=0,fps=None))
        for label,fps in [('Target40',10),('Target120',30),('AppSaturation',None)]:
            for mode in ((1,2) if repetition%2==0 else (2,1)):
                plan.append(dict(name=f'r{repetition+1}-{label}-'+('Full' if mode==1 else 'Compact'),mode=mode,fps=fps))
        plan.append(dict(name=f'r{repetition+1}-PLContinuous',mode=3,fps=None))
    return [dict(p,**profiles.metadata(profile),seconds=seconds,scan_ms=20,offset_ms=0) for p in plan]


def selected_formal_plan(seconds=120,repetitions=5,target120_only=False,profile=profiles.STRICT):
    plan=formal_plan(seconds,repetitions,profile)
    return [p for p in plan if '-Target120-' in p['name']] if target120_only else plan


def portable_key(name):
    """Normalize legacy Windows separators without accepting unsafe aliases."""
    if not isinstance(name,str) or not name or '\x00' in name or ':' in name:
        raise GateError('unsafe relative evidence path')
    key=name.replace('\\','/')
    if any(part in ('','.','..') for part in key.split('/')):
        raise GateError('unsafe relative evidence path: '+repr(name))
    return key


def relative_key(path,directory):
    return portable_key(path.relative_to(directory).as_posix())


def normalize_inventory(recorded):
    """In-memory comparison only; do not rewrite bytes bound by raw hashes."""
    if not isinstance(recorded,dict):raise GateError('malformed evidence inventory')
    normalized={}
    for name,entry in recorded.items():
        key=portable_key(name)
        if key in normalized:raise GateError('colliding evidence inventory paths: '+key)
        normalized[key]=entry
    return normalized


def inventory(directory):
    directory=pathlib.Path(directory);result={}
    for p in sorted(directory.rglob('*')):
        if not p.is_file() or p.name in ('session.json','inventory.json'):continue
        key=relative_key(p,directory)
        if key in result:raise GateError('colliding filesystem evidence paths: '+key)
        result[key]=dict(bytes=p.stat().st_size,sha256=file_hash(p))
    return result


def phase_relative_path(session,index,plan):
    expected=portable_key(f'phases/{index:03d}-{plan["name"]}')
    phases=session.get('phases',[])
    if index<len(phases):
        actual=portable_key(phases[index]['path'])
        if actual!=expected:raise GateError('saved phase path differs from ordered plan')
    return expected


def evidence_lines(path):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise GateError('duplicate raw evidence key')
            result[key]=value
        return result
    try:
        rows=[json.loads(line,object_pairs_hook=pairs,
            parse_constant=lambda x:(_ for _ in ()).throw(GateError('nonfinite raw evidence')))
            for line in pathlib.Path(path).read_text(encoding='utf-8').splitlines()]
        if not rows or any(not isinstance(r,dict) for r in rows):raise GateError('empty/malformed raw evidence: '+str(path))
        return rows
    except (OSError,ValueError) as exc:raise GateError('missing/malformed raw evidence: '+str(path)) from exc


def validate_toggle_evidence(directory,comparison,input_sha256,profile=profiles.STRICT):
    """Reassess required raw records; a matching aggregate/inventory is insufficient."""
    directory=pathlib.Path(directory);request_ids=set()
    def host_tick(value):
        if type(value) not in (int,float) or not math.isfinite(value):raise GateError('invalid host timestamp')
        return value
    try:
        for enabled,run in enumerate(comparison):
            require_profile(run,profile)
            require_profile(run['setting_status'],profile,sampler=True)
            require_profile(run['observed_status'],profile,sampler=True)
            setting=run['setting_status'];hz=setting['timer_hz']
            if (setting['mode']!=2 or setting['scan_ms'] not in (17,20,23) or
                not 0<=setting['offset_ms']<setting['scan_ms']):raise GateError('invalid toggle settings')
            observations=evidence_lines(directory/f'sampling{enabled}-observations.jsonl')
            previous=None;stable=None;qualified=False
            for observation in [dict(host_monotonic=None,status=setting)]+observations:
                s=observation['status'];heartbeat=s['sampler_heartbeat'];now=s['now_ticks']
                validate_condition(s,setting,sampling_enabled=enabled)
                if (s['schema']!=1 or s['physical_status']!='NOT_RUN' or s['snapshot_valid'] is not True or
                    s['service_core']!=0 or s['sampler_core']!=1 or type(hz) is not int or hz<=0 or
                    s['timer_hz']!=hz or s['sampler_hz']!=hz or s['epoch']!=setting['epoch'] or
                    s['sampler_epoch']!=s['epoch'] or s['configured_mask']!=262143 or
                    not profiles.qualified(s,profile) or
                    now-s['configured_tick']<hz or s['clock_checks']<3 or s['heartbeat_advances']<3 or
                    s['faults'] or s['sampler_faults'] or any(s[k] for k in COUNTERS) or
                    not 0<=now-heartbeat<=hz/4 or s['temperature_valid']!=1 or
                    not 0<=now-s['temperature_tick']<=2*hz or not -55000<=s['temperature_mC']<=150000):
                    raise GateError('unhealthy raw toggle status/clock/configuration')
                if observation['host_monotonic'] is None:continue
                host=host_tick(observation['host_monotonic'])
                if previous and (host<=previous[0] or heartbeat<=previous[1]['sampler_heartbeat'] or
                    now<=previous[1]['now_ticks'] or s['scan_count']<previous[1]['scan_count']):
                    raise GateError('nonadvancing/backwards raw toggle observations')
                qualified=False
                if heartbeat>setting['now_ticks']:
                    if enabled:qualified=s['ready'] is True and s['scan_count']>setting['scan_count']
                    elif previous and s['scan_count']==previous[1]['scan_count'] and stable is not None:
                        qualified=(heartbeat-stable[1]>=.046*hz and host-stable[0]>=.046-1e-12)
                    else:stable=(host,heartbeat)
                else:stable=None
                previous=(host,s)
            kind='ready_and_scan_progress' if enabled else 'inferred_off_from_stable_scan_count'
            if not qualified or run['observed_status']!=observations[-1]['status'] or run['observation_kind']!=kind:
                raise GateError('raw sampler off/on behavior not established')
            frames=evidence_lines(directory/f'throughput-sampling{enabled}.jsonl')
            first,last=frames[0],frames[-1]
            start=host_tick(first['host_monotonic']);end=host_tick(last['host_monotonic'])
            if (first['event']!='interval_start' or last['event']!='interval_end' or
                first['sampling_enabled']!=enabled or last['sampling_enabled']!=enabled or
                run['interval_monotonic']!=[start,end] or end-start<5 or
                abs(run['elapsed_seconds']-(end-start))>1e-9 or previous[0]>start):
                raise GateError('raw throughput interval/duration mismatch')
            pending=None;submitted=None;completed=0;last_received=start
            for frame in frames[1:-1]:
                event=frame['event'];key=(frame['stream'],frame['sequence'])
                if frame['phase']!='throughput-comparison' or frame['input_sha256']!=input_sha256:
                    raise GateError('raw toggle frame phase/input identity mismatch')
                if event=='produced':
                    produced=host_tick(frame['produced_monotonic'])
                    if pending is not None or not last_received<=produced<=end:raise GateError('invalid closed-loop production')
                    pending=(key,produced);submitted=None
                elif event=='submitted':
                    stamp=host_tick(frame['submitted_monotonic']);rid=frame['request_id']
                    if (not pending or key!=pending[0] or submitted is not None or rid in request_ids or
                        type(rid) is not int or not 0<rid<=0xffffffff or not pending[1]<=stamp<=end):
                        raise GateError('invalid/duplicate closed-loop submission')
                    request_ids.add(rid);submitted=(rid,stamp)
                elif event=='completed':
                    received=host_tick(frame['received_monotonic']);meta=frame['board_response']
                    if (not pending or key!=pending[0] or not submitted or frame['request_id']!=submitted[0] or
                        frame['verified'] is not True or not submitted[1]<=received<=end or
                        abs(frame['e2e_seconds']-(received-pending[1]))>1e-9 or
                        abs(frame['transaction_seconds']-(received-submitted[1]))>1e-9):
                        raise GateError('unverified/inconsistent raw throughput completion')
                    try:wire.validate_business_metadata(meta,'replay_compact',hz)
                    except wire.ProtocolError as exc:raise GateError('raw throughput inference/output verification mismatch') from exc
                    completed+=1;last_received=received;pending=None;submitted=None
                else:raise GateError('failure/unexpected raw throughput event')
            if pending or submitted or completed<=0 or run['completed']!=completed or run['failed']!=0:
                raise GateError('raw throughput count/incomplete transaction mismatch')
    except (KeyError,TypeError,ValueError,IndexError) as exc:
        raise GateError('missing/malformed sampler-toggle raw evidence') from exc


def validate_acceptance(path,identity,board_id,controls):
    path=pathlib.Path(path).resolve()
    s=read_json(path);profile=identity['measurement_profile']
    require_profile(s,profile)
    if s.get('identity')!=identity or s.get('source_hashes')!=source_hashes():
        raise IdentityError('acceptance firmware/source identity mismatch')
    for plan_row in s.get('plan',[]):require_profile(plan_row,profile)
    for phase_row in s.get('phases',[]):require_profile(phase_row,profile)
    if (s.get('schema')!='e07-host-session-v1' or s.get('kind')!='acceptance' or
        s.get('status')!='COMPLETE' or s.get('physical') is not True or
        s.get('peer_ip')!='192.168.10.2' or s.get('board_id')!=board_id or
        s.get('controls')!=controls or s.get('plan')!=acceptance_plan(profile)):
        raise GateError('formal run requires matching successful physical short-acceptance dataset')
    recorded=read_json(path.parent/'inventory.json')
    if normalize_inventory(recorded)!=inventory(path.parent):raise IdentityError('acceptance raw evidence inventory mismatch')
    validate_receipt_value(ROOT,s.get('sd_receipt',{}),profile)
    validate_status(read_json(path.parent/'startup-status.json'),profile=profile)
    if read_json(path.parent/'hello.json')!=wire.expected_greeting(identity):
        raise IdentityError('acceptance firmware greeting mismatch')
    if s.get('manifest')!=read_json(path.parent/'manifest.json') or s['manifest']!=s['sd_receipt']['files'] or read_json(path.parent/'firmware-identity.json')!=identity:
        raise IdentityError('acceptance manifest/identity mismatch')
    comparison=read_json(path.parent/'throughput-comparison.json')
    for run in [*comparison,*s['throughput_comparison']]:
        require_profile(run,profile)
        require_profile(run['setting_status'],profile,sampler=True)
        require_profile(run['observed_status'],profile,sampler=True)
    if s.get('throughput_comparison')!=comparison:
        raise GateError('missing raw sampler on/off throughput evidence')
    for run in s['throughput_comparison']:
        if run.get('completed',0)<=0 or run.get('failed') or run.get('elapsed_seconds',0)<5:
            raise GateError('sampler on/off acceptance failed')
    if [r.get('sampling_enabled') for r in s['throughput_comparison']]!=[0,1]:
        raise GateError('sampler throughput comparison incomplete')
    validate_toggle_evidence(path.parent,s['throughput_comparison'],identity['artifact_hashes']['input'],profile)
    for index,p in enumerate(acceptance_plan(profile)):
        phase_dir=path.parent/phase_relative_path(s,index,p)
        saved=read_json(phase_dir/'phase.json')
        require_profile(saved,profile)
        if any(saved.get(k)!=v for k,v in p.items()):raise GateError('acceptance condition mismatch')
        assess_phase(phase_dir,profile,identity['artifact_hashes']['input'])
    return dict(**profiles.metadata(profile),path=str(path),sha256=file_hash(path),inventory_sha256=file_hash(path.parent/'inventory.json'),
                acceptance_scope='strict18 power and capture' if profile==profiles.STRICT else 'diagnostic capture; power quality evaluated separately')


class Journal:
    def __init__(self,path):
        self.stream=pathlib.Path(path).open('x',encoding='utf-8')
        self.lock=threading.Lock()

    def __call__(self,event):
        with self.lock:
            self.stream.write(json.dumps(event,sort_keys=True,allow_nan=False)+'\n')
            self.stream.flush()

    def close(self):
        self.stream.close()


class Runner:
    def __init__(self,client,output,fixture,input_sha256):
        self.client=client;self.output=pathlib.Path(output);self.fixture=fixture
        self.input_sha256=input_sha256

    def serve_frame(self,producer,mode,record,phase):
        if producer:
            frame=producer.pop()
            if frame is None:return False
        else:
            frame=dict(stream=None,sequence=self.client.next_id,phase=phase,
                input_sha256=self.input_sha256,planned_monotonic=None,produced_monotonic=time.monotonic(),state='queued')
            record(dict(frame,event='produced'))
        rid=self.client.next_id
        if producer:producer.submit(frame,rid)
        else:
            frame.update(request_id=rid,submitted_monotonic=time.monotonic())
            record(dict(frame,event='submitted'))
        try:
            r=self.client.business('replay_full' if mode==1 else 'replay_compact',self.fixture)
            if producer:producer.complete(frame,r.received_monotonic,True,response_metadata=r.metadata)
            else:record(dict(frame,event='completed',received_monotonic=r.received_monotonic,verified=True,
                e2e_seconds=r.received_monotonic-frame['produced_monotonic'],
                transaction_seconds=r.received_monotonic-frame['submitted_monotonic'],board_response=r.metadata))
        except Exception as exc:
            if producer:producer.complete(frame,time.monotonic(),False,str(exc),failure_type=type(exc).__name__)
            else:record(dict(frame,event='failed',received_monotonic=time.monotonic(),error=str(exc),failure_type=type(exc).__name__))
            raise
        return True

    def comparison(self):
        results=[]
        for enabled in (0,1):
            self.client.request('power_load',2)
            setting=self.client.request('power_sampling',enabled).metadata
            observed=wait_sampling_observed(self.client,setting,enabled,self.output)
            start=time.monotonic();completed=0
            log=Journal(self.output/f'throughput-sampling{enabled}.jsonl')
            try:
                log(dict(event='interval_start',host_monotonic=start,sampling_enabled=enabled))
                while time.monotonic()-start<5:
                    self.serve_frame(None,2,log,'throughput-comparison');completed+=1
                end=time.monotonic()
                log(dict(event='interval_end',host_monotonic=end,sampling_enabled=enabled))
                results.append(dict(**profiles.metadata(self.client.profile),sampling_enabled=enabled,completed=completed,failed=0,
                    setting_status=setting,observed_status=observed,
                    observation_kind='inferred_off_from_stable_scan_count' if not enabled else 'ready_and_scan_progress',
                    elapsed_seconds=end-start,interval_monotonic=[start,end],throughput_scope='closed-loop host throughput only'))
            finally:log.close()
        self.client.request('power_sampling',1)
        self.client.request('power_load',0)
        wire.save_json(self.output/'throughput-comparison.json',results)
        return results

    def recover(self,directory,arm):
        """Bounded evidence recovery; preserve original failure and never release."""
        log=Journal(directory/'recovery-observations.jsonl')
        result=dict(status='INCOMPLETE',exports={},started_host_monotonic=time.monotonic())
        original_timeout=self.client.sock.gettimeout()
        # Maximum valid formal phase150s plus arm lead, postguard and5s slack.
        deadline=time.monotonic()+158
        try:
            first=True
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise GateError('recovery scheduled postguard deadline expired')
                self.client.sock.settimeout(min(original_timeout or remaining,remaining))
                s=self.client.status()
                log(dict(host_monotonic=time.monotonic(),status=s))
                result['final_status']=s
                if first:
                    wire.save_json(directory/'recovery-status.json',s)
                    remaining_board=max(0,(arm['t1']+arm['timer_hz']-s['now_ticks'])/arm['timer_hz'])
                    deadline=min(deadline,time.monotonic()+remaining_board+5)
                    result['deadline_host_monotonic']=deadline
                    first=False
                if (not s['snapshot_valid'] or s['timer_hz']!=arm['timer_hz'] or
                    s['phase_id']!=arm['phase_id'] or s['t0']!=arm['t0'] or s['t1']!=arm['t1']):
                    raise GateError('recovery phase/clock identity mismatch')
                if not 0<=s['now_ticks']-s['sampler_heartbeat']<=s['timer_hz']/4:
                    raise GateError('recovery sampler heartbeat stale/stopped')
                if s['now_ticks']>=s['t1']+s['timer_hz'] and s['sampler_state']==4:
                    if s['state']!=4:
                        try:finished=self.client.request('power_finish').metadata
                        except wire.BoardError as exc:
                            if exc.metadata.get('code')!='phase_state':raise
                            time.sleep(.05);continue
                        result['final_status']=finished
                    break
                time.sleep(.05)
            wire.save_json(directory/'recovery-end-status.json',result['final_status'])
            for kind in ('config','rails','events','temperatures'):
                try:
                    self.client.export(kind,directory/'recovery-exports',arm['phase_id'])
                    result['exports'][kind]='EXPORTED'
                except Exception as exc:
                    result['exports'][kind]=dict(status='INCOMPLETE',type=type(exc).__name__,detail=str(exc))
            if all(value=='EXPORTED' for value in result['exports'].values()):result['status']='EXPORTED'
            else:result['error']='one or more raw exports failed'
        except BaseException as exc:
            result['error']=dict(type=type(exc).__name__,detail=str(exc))
        finally:
            try:self.client.sock.settimeout(original_timeout)
            except OSError as exc:result['timeout_restore_error']=str(exc)
            result['finished_host_monotonic']=time.monotonic()
            wire.save_json(directory/'recovery-result.json',result)
            log.close()
        return result

    def phase(self,index,p):
        if not profiles.matches(p,self.client.profile):raise GateError("phase plan profile mismatch")
        directory=self.output/'phases'/f'{index:03d}-{p["name"]}'
        directory.mkdir(parents=True,exist_ok=False)
        journal=Journal(directory/'frame-events.jsonl')
        temperatures=Journal(directory/'temperature-cache.jsonl')
        phase_status=Journal(directory/'phase-status.jsonl')
        producer=None;phase_info=dict(p,status='INCOMPLETE');armed=False
        closed=[];host_window=None
        def record(e):
            journal(e)
            if e['event'] in ('completed','failed'):closed.append(e)
        try:
            # Reset offset before reducing the scan period.
            self.client.request('power_offset',0)
            self.client.request('power_scan',p['scan_ms'])
            self.client.request('power_offset',p['offset_ms'])
            self.client.request('power_sampling',1)
            selected=self.client.request('power_load',p['mode']).metadata
            validate_condition(selected,p)
            if p['fps']:
                producer=load.OfferedLoad(p['fps'],record,phase=p['name'],input_sha256=self.input_sha256)
                producer.start()
            warm_start=time.monotonic();last_status=0;warm=[];status=None
            while True:
                now=time.monotonic()
                if now-last_status>=1:
                    status=self.client.status();temperatures(dict(host_monotonic=now,status=status))
                    validate_status(status,profile=self.client.profile)
                    validate_condition(status,p)
                    warm.append(status);last_status=now
                    if warmup_ready(self.client.profile,now-warm_start,warm):break
                    if now-warm_start>=600:raise GateError('THERMAL_NOT_STABLE')
                if p['mode'] in (1,2):
                    if not self.serve_frame(producer,p['mode'],record,p['name']):time.sleep(.001)
                else:time.sleep(.01)
            wire.save_json(directory/'warmup-temperatures.json',warm)
            phase_info.update(warmup_elapsed_seconds=time.monotonic()-warm_start,
                warmup_policy='strict-stability' if self.client.profile==profiles.STRICT else 'diagnostic-minimum-30s',
                warmup_thermal_stable=thermal_stable(warm))
            start=ensure_ready(self.client,directory)
            validate_condition(start,p)
            # Cache config/latest before arm; later export is DONE only.
            config=self.client.export('config',directory/'prearm')
            validate_config(config)
            wire.save_json(directory/'start-status.json',start)
            try:
                arm=self.client.request('power_arm',p['seconds']).metadata
            except Exception:
                diagnostics(self.client,directory);raise
            armed=True
            phase_info.update(board_phase_id=arm['phase_id'],board_t0=arm['t0'],board_t1=arm['t1'],
                timer_hz=arm['timer_hz'],arm_status=arm)
            wire.save_json(directory/'armed.json',phase_info)
            validate_condition(arm,p)
            # A separate host window is anchored on complete arm response receipt.
            # It intentionally does not map board ticks onto host monotonic.
            host_start=time.monotonic();host_window=(host_start,host_start+p['seconds'])
            phase_info['host_window_monotonic']=list(host_window)
            phase_info['host_window_definition']='[arm response receipt, receipt + configured seconds); independent of board energy window'
            if producer:producer.window=host_window
            status=arm;last_status=0
            deadline=time.monotonic()+p['seconds']+15
            while True:
                now=time.monotonic()
                if now-last_status>=.1:
                    status=self.client.status();last_status=now
                    phase_status(dict(host_monotonic=now,status=status))
                    validate_condition(status,p)
                    if status['faults'] or status['sampler_faults']:
                        phase_info['observed_faults']=dict(faults=status['faults'],sampler_faults=status['sampler_faults'])
                    if status['now_ticks']>=status['t1']+status['timer_hz'] and status['sampler_state']==4:break
                    if now>deadline:raise GateError('board phase/postguard deadline did not complete')
                if p['mode'] in (1,2) and not phase_info.get('observed_faults'):
                    if not self.serve_frame(producer,p['mode'],record,p['name']):time.sleep(.001)
                else:time.sleep(.005)
            if producer:
                producer.stop()
                # The queues are drained after postguard; each completion stays outside
                # the host window when its actual receive timestamp is outside it.
                while any(producer.queues):self.serve_frame(producer,p['mode'],record,p['name'])
            for attempt in range(100):
                try:
                    end=self.client.request('power_finish').metadata;break
                except wire.BoardError as exc:
                    if exc.metadata.get('code')!='phase_state' or attempt==99:raise
                    time.sleep(.05)
            wire.save_json(directory/'end-status.json',end)
            validate_condition(end,p)
            for kind in ('config','rails','events','temperatures'):
                self.client.export(kind,directory/'exports',end['phase_id'])
            if producer:counts=producer.counts()
            else:
                completed=[e for e in closed if e['event']=='completed']
                counts=dict(produced=len(closed),submitted=len(closed),completed=len(completed),
                    completed_window=sum(host_window[0]<=e['received_monotonic']<host_window[1] for e in completed),
                    completed_drain=sum(e['received_monotonic']>=host_window[1] for e in completed),
                    failed=sum(e['event']=='failed' for e in closed),remaining=0,in_flight=0,
                    timeouts=sum(e.get('failure_type') in ('TimeoutError','timeout') for e in closed),
                    host_fps=sum(host_window[0]<=e['received_monotonic']<host_window[1] for e in completed)/p['seconds'],
                    evicted=0,missed_slots=0,conserved=True,offer_definition='closed-loop' if p['mode'] in (1,2) else 'none')
            phase_info['status']='EXPORTED'
            wire.save_json(directory/'host-counts.json',counts)
            wire.save_json(directory/'phase.json',phase_info)
            evidence=assess_phase(directory,self.client.profile,self.input_sha256)
            wire.save_json(directory/'acceptance-evidence.json',evidence)
            self.client.request('power_release')
            for n in range(100):
                status=self.client.status()
                if status['sampler_state']==0 and status['rail_records']==status['temperature_records']==0:break
                time.sleep(.05)
            else:raise GateError('sampler did not acknowledge log release')
            return dict(path=relative_key(directory,self.output),status='COMPLETE',**evidence)
        except BaseException as exc:
            phase_info.update(status='INCOMPLETE',error=dict(type=type(exc).__name__,detail=str(exc)),armed=armed)
            wire.save_json(directory/'failure.json',phase_info)
            # Best-effort freeze/export on failure: never erase records or release.
            if armed:
                if producer:producer.stop()
                self.recover(directory,arm)
            else:
                if not (directory/'diagnostics').exists():diagnostics(self.client,directory)
            raise
        finally:
            if producer:
                producer.stop()
                if not (directory/'host-counts.json').exists():wire.save_json(directory/'host-counts.json',producer.counts())
            journal.close();temperatures.close();phase_status.close()


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--package-root',type=pathlib.Path,default=ROOT)
    action=p.add_mutually_exclusive_group(required=True)
    action.add_argument('--check-only',action='store_true',help='package preflight only; no board or result directory')
    action.add_argument('--prepare-sd',action='store_true',help='verify actual mounted SD contents and save receipt; no board')
    action.add_argument('--acceptance',action='store_true',help='physical short/startup + 17/23 ms, two-offset, 60-second checks')
    action.add_argument('--formal',action='store_true',help='paired formal suite; requires raw physical acceptance dataset')
    scope=p.add_mutually_exclusive_group()
    scope.add_argument('--diagnostic17',action='store_true',help='exclude Rail7; keep negative-only diagnostic records')
    scope.add_argument('--diagnostic16',action='store_true',help='exclude Rail7/Rail15; 16-rail diagnostic capture')
    p.add_argument('--target120-only',action='store_true',help='with --formal only: paired Target120 Full/Compact; default remains full suite')
    p.add_argument('--sd-root',type=pathlib.Path,help='actual copied SD root while mounted on host')
    p.add_argument('--sd-receipt',type=pathlib.Path,help='tool-generated verification receipt to write/consume')
    p.add_argument('--acceptance-session',type=pathlib.Path,help='successful physical acceptance session.json')
    p.add_argument('--output',type=pathlib.Path,help='new session directory; never overwrites existing results')
    p.add_argument('--listen',default='192.168.10.1',help='host listen address; board initiates connection')
    p.add_argument('--port',type=int,default=5001)
    p.add_argument('--timeout',type=float,default=15,help='per socket transaction/accept timeout seconds')
    p.add_argument('--board-id',help='physical board identifier, manually read from the same board for every session')
    p.add_argument('--controls',type=pathlib.Path,help='JSON object recording clocks, power, fan, network and environment')
    p.add_argument('--seconds',type=int,default=120,help='formal seconds per condition (default 120, max 150)')
    p.add_argument('--repetitions',type=int,default=5,help='paired repetitions (default 5)')
    return p


def verify_delivery(root):
    from package import verify_package,PackageError
    development=(len(root.parents)>2 and (root.parents[2]/'Cloud_test/e07/vendor/e07_base').is_dir()
                 and (root/'execution/original_hashes.json').is_file())
    if (root/'PACKAGE_SHA256SUMS.json').exists() or not development:
        try:verify_package(root)
        except PackageError as exc:raise GateError(str(exc)) from exc


def main(argv=None):
    args=parser().parse_args(argv)
    if sys.version_info<(3,11):raise GateError('Python 3.11+ required')
    if args.target120_only and not args.formal:raise GateError('--target120-only requires --formal')
    root=args.package_root.resolve()
    if not args.check_only:
        for label,path in (('output',args.output),('SD receipt',args.sd_receipt),('controls',args.controls)):
            if path is not None and path.resolve().is_relative_to(root):
                raise GateError(label+' must be outside the immutable package directory')
    profile=profiles.DIAGNOSTIC16 if args.diagnostic16 else profiles.DIAGNOSTIC if args.diagnostic17 else profiles.STRICT
    verify_delivery(root)
    if root!=ROOT and source_hashes(root)!=source_hashes(ROOT):
        raise GateError('running host differs from selected package source')
    info=preflight(root,profile)
    if args.check_only:
        print(json.dumps(dict(**profiles.metadata(profile),status='PACKAGE_PREFLIGHT_PASS',firmware_sha256=info['identity']['firmware_sha256'],
            copied_SD='NOT_CHECKED' if not args.sd_root else 'CHECK_REQUIRED_VIA_PREPARE_SD',
            physical_startup='NOT_RUN',power_acceptance='NOT_RUN')))
        return 0
    if args.prepare_sd:
        if not args.sd_root or not args.sd_receipt:raise GateError('--prepare-sd requires --sd-root and --sd-receipt')
        receipt=verify_sd(root,args.sd_root,args.sd_receipt,profile)
        print(json.dumps(dict(**profiles.metadata(profile),status='SD_COPY_VERIFIED',receipt=str(args.sd_receipt),assumption=receipt['assumption'])))
        return 0
    if args.sd_root:
        if not args.sd_receipt:raise GateError('--sd-root requires --sd-receipt destination')
        verify_sd(root,args.sd_root,args.sd_receipt,profile)
    if not args.sd_receipt:raise GateError('verify mounted SD first with --prepare-sd; --sd-receipt required')
    receipt=validate_receipt(root,args.sd_receipt,profile)
    if not args.output or not args.board_id or not args.controls:
        raise GateError('physical runs require --output, --board-id and --controls')
    controls=read_json(args.controls)
    required=('cpu_clock','pl_clock','power_supply','fan','network','environment')
    if not isinstance(controls,dict) or any(not controls.get(k) for k in required):
        raise GateError('controls JSON requires '+', '.join(required))
    if not 1<=args.seconds<=150 or args.repetitions<1:raise GateError('invalid formal duration/repetitions')
    acceptance=None
    if args.formal:
        if not args.acceptance_session:raise GateError('--formal requires --acceptance-session raw dataset')
        acceptance=validate_acceptance(args.acceptance_session,info['identity'],args.board_id,controls)
    plan=acceptance_plan(profile) if args.acceptance else selected_formal_plan(args.seconds,args.repetitions,args.target120_only,profile)
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    session=dict(**profiles.metadata(profile),schema='e07-host-session-v1',kind='acceptance' if args.acceptance else 'formal',
        status='INCOMPLETE',started_utc=utcnow(),identity=info['identity'],manifest=info['manifest'],
        package_manifest_sha256=info['manifest_sha256'],sd_receipt=receipt,source_hashes=source_hashes(root),
        os=platform.platform(),python=sys.version,board_id=args.board_id,controls=controls,
        plan=plan,acceptance_binding=acceptance,physical=False,phases=[],
        selected_profile='acceptance' if args.acceptance else ('target120-only' if args.target120_only else 'full-suite'),
        qualification='New candidate physical startup and power acceptance were NOT_RUN at package delivery.',
        acceptance_scope='strict18 power and capture' if profile==profiles.STRICT else 'diagnostic capture; negative-only records do not abort, power quality is separate')
    wire.save_json(out/'session-start.json',session)
    wire.save_json(out/'manifest.json',info['manifest'])
    wire.save_json(out/'firmware-identity.json',info['identity'])
    protocol_log=Journal(out/'protocol-events.jsonl')
    sock=None
    try:
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            listener.bind((args.listen,args.port));listener.listen(1);listener.settimeout(args.timeout)
            print(f'Listening on {args.listen}:{args.port}; boot the verified SD card.',flush=True)
            sock,peer=listener.accept()
        sock.settimeout(args.timeout)
        sock.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
        session['peer_ip']=peer[0]
        session['physical']=physical_peer(peer[0]) and peer[0]=='192.168.10.2'
        if not session['physical']:raise GateError('simulation/wrong board peer cannot count as physical evidence')
        client=wire.Client(sock,info['identity'],protocol_log,out/'raw-wire')
        wire.save_json(out/'hello.json',client.hello.metadata)
        startup=ensure_ready(client,out)
        wire.save_json(out/'startup-status.json',startup)
        config=client.export('config',out/'startup-exports');validate_config(config)
        runner=Runner(client,out,(root/profiles.paths(profile)[2]/'input.bin').read_bytes(),info['identity']['artifact_hashes']['input'])
        if args.acceptance:session['throughput_comparison']=runner.comparison()
        for index,p in enumerate(plan):session['phases'].append(runner.phase(index,p))
        session['status']='COMPLETE'
    except BaseException as exc:
        session['error']=dict(type=type(exc).__name__,detail=str(exc),traceback=traceback.format_exc())
    finally:
        if sock:sock.close()
        protocol_log.close()
        session['finished_utc']=utcnow()
        session['capture_complete']=session['status']=='COMPLETE'
        session['power_quality_valid']=bool(session['phases']) and all(p.get('power_quality_valid') is True for p in session['phases'])
        session['warmup_thermal_stable_for_all_phases']=bool(session['phases']) and all(p.get('warmup_thermal_stable') is True for p in session['phases'])
        wire.save_json(out/'inventory.json',inventory(out))
        wire.save_json(out/'session.json',session)
    print(json.dumps(dict(**profiles.metadata(profile),status=session['status'],capture_complete=session['capture_complete'],
        power_quality_valid=session['power_quality_valid'],warmup_thermal_stable_for_all_phases=session['warmup_thermal_stable_for_all_phases'],
        session=str(out/'session.json'),error=session.get('error',{}).get('detail'))))
    return 0 if session['status']=='COMPLETE' else 1


if __name__=='__main__':
    try:sys.exit(main())
    except (GateError,wire.ProtocolError,OSError,ValueError,KeyError) as exc:
        print(f'FAILED: {exc}',file=sys.stderr);sys.exit(2)
