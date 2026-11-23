"""Synthetic mathematics and literal schema-1 binary evidence; no physical data.

These catch extrapolation, clock/count mixing, discarded invalid records,
trust of edited decoded JSON, and permissive package preflight.
"""
import copy
import importlib
import json
import pathlib
import shutil
import subprocess
import struct
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    analyze = importlib.import_module('host.analyze')
except ModuleNotFoundError:
    analyze = None
try:
    package = importlib.import_module('package')
except ModuleNotFoundError:
    package = None


STRICT=dict(measurement_profile='strict18',included_mask=262143,included_count=18,excluded_rails=[],
            scope='18 monitored supply rails; not external whole-board input power')
DIAG=dict(measurement_profile='diagnostic17',included_mask=262015,included_count=17,excluded_rails=[7],
          scope='17-rail diagnostic')

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def fixture_status(**changes):
    value = dict(**STRICT,observed_mask=262143,excluded_negative_samples=0,included_negative_samples=0,sampler_profile_rails=18,schema=1, physical_status='NOT_RUN', ready=True, snapshot_valid=True,
        phase_id=1, state=4, faults=0, sampler_faults=0, service_core=0, sampler_core=1,
        epoch=7, sampler_epoch=7, timer_hz=8000, sampler_hz=8000, now_ticks=104100,
        sampler_heartbeat=104000, clock_checks=4, heartbeat_advances=4, configured_mask=262143,
        configured_tick=8000,conversion_ready_mask=262143,initializing_samples=18,
        mode=1, sampling_enabled=1, scan_ms=20, offset_ms=0,
        t0=80000, t1=96000, sampler_phase=1, sampler_state=4, rail_records=594,
        event_records=244, temperature_records=5, scan_count=500, completed_full=240,
        completed_compact=0, completed_continuous=0, continuous_begin=0, continuous_end=0,
        pending_ack=0, temperature_mC=45000, temperature_valid=1, temperature_tick=104000,
        i2c_errors=0, invalid_samples=0, stale_samples=0, scan_overruns=0, overflows=0,
        temperature_errors=0)
    value.update(changes)
    return value


def math_rows():
    # Independent literal formula: integral_0^2(2+t)dt=6 J; sample gap100ms.
    return [dict(rail=0, flags=3, begin=[i*1000]*5, end=[i*1000]*5,
                 power_uW=2000000+i*100000, scan_start=i*1000)
            for i in range(21)]


class RawFixture:
    """Full literal export layout;125ms permits exact Power codes on all rails."""
    def __init__(self, directory):
        self.directory = directory
        self.rails = []
        for scan in range(33):
            tick = 72000+scan*1000  # board9..13s, window10..12s;125ms.
            power = 1000000+scan*125000  # P=2+(board_time-10)W.
            for rail in range(18):
                self.rails.append(dict(seq=len(self.rails), phase=1, scan=scan, flags=3,
                    rail=rail, config=0x4527, calibration=2048, shunt=10, bus=800,
                    current=100, power=power//(31250 if rail==10 else 12500), mask=8,
                    begin=[tick-8,tick-6,tick-4,tick-1,tick-10],
                    end=[tick-7,tick-5,tick-3,tick+1,tick-9],power_uW=power,scan_start=tick-11))
        self.config = [dict(rail=r, flags=1, manufacturer=0x5449, die=0x2260,
            config=0x4527, calibration=2048, begin=100, end=101) for r in range(18)]
        def event(typ, tick, **kw):
            e=dict(seq=0,phase=1,type=typ,request_id=0,mode=1,flags=0,mismatch_count=0,
                   reserved=0,begin=0,end=0,tick=tick,aux=0)
            e.update(kw)
            return e
        self.events=[event(1,70000,begin=80000,end=96000),event(2,80000)]
        for i in range(240):
            tick=80000+i*66
            self.events.append(event(5,tick,request_id=i+1,flags=1,begin=tick-10,end=tick-5))
        self.events.extend([event(3,96000),event(4,104001)])
        self.temps=[dict(seq=i,phase=1,flags=1,raw=30000,tick=72000+i*8000,
                         temperature_mC=45000,reserved=0) for i in range(5)]
        self.end=fixture_status()
        self.start=fixture_status(phase_id=0,state=0,sampler_state=0,t0=0,t1=0)
        self.phase=dict(**STRICT,name='r1-Target120-Full',mode=1,fps=30,seconds=2,scan_ms=20,
            offset_ms=0,board_phase_id=1,board_t0=80000,board_t1=96000,timer_hz=8000,
            arm_status=fixture_status(state=1,sampler_state=1),
            host_window_monotonic=[1000.0,1002.0],warmup_elapsed_seconds=30.,status='EXPORTED')
        self.warm=[fixture_status(now_ticks=(i+40)*8000,sampler_heartbeat=(i+40)*8000-1,temperature_tick=(i+40)*8000)
                   for i in range(31)]
        self.host=dict(produced=240,submitted=240,completed=240,failed=0,remaining=0,in_flight=0,
            evicted=0,missed_slots=0,scheduled_slots=240,timeouts=0,completed_window=1,
            completed_pre_window=0,completed_drain=239,host_fps=.5,conserved=True)
        self.frames=[]
        for i in range(240):
            produced=1000.+i/120
            received=1001. if i==0 else 1003.+i/120
            base=dict(stream=0,sequence=i,phase=self.phase['name'],input_sha256='a'*64,
                      produced_monotonic=produced,planned_monotonic=produced)
            self.frames.append(dict(base,event='produced'))
            self.frames.append(dict(base,event='submitted',request_id=i+1,submitted_monotonic=produced))
            self.frames.append(dict(base,event='completed',request_id=i+1,submitted_monotonic=produced,
                received_monotonic=received,verified=True,board_response=dict(fixture='E07_FIXED_INPUT',mode='replay_full',
                    edge_rx_start_ticks=100,edge_rx_end_ticks=101,inference_start_ticks=102,inference_end_ticks=103,
                    result_queue_ticks=104,timer_frequency_hz=8000,mismatch_count=0,predicted_class=0,total_ticks=1),e2e_seconds=received-produced,
                transaction_seconds=received-produced))

    def save(self):
        import hashlib
        from host import wire
        self.end.update(rail_records=len(self.rails),event_records=len(self.events),temperature_records=len(self.temps))
        for kind,rows in [('rails',self.rails),('config',self.config),('events',self.events),('temperatures',self.temps)]:
            for i,row in enumerate(rows):
                if kind!='config':row['seq']=i
            for first in range(0,len(rows),256):
                chunk=rows[first:first+256]
                values=[]
                for r in chunk:
                    if kind=='rails':
                        v=[r[k] for k in ('seq','phase','scan','flags','rail','config','calibration',
                            'shunt','bus','current','power','mask')]+r['begin']+r['end']+[r['power_uW'],r['scan_start']]
                    elif kind=='events':
                        v=[r[k] for k in ('seq','phase','type','request_id','mode','flags','mismatch_count',
                                          'reserved','begin','end','tick','aux')]
                    elif kind=='config':
                        v=[r[k] for k in ('rail','flags','manufacturer','die','config','calibration','begin','end')]
                    else:v=[r[k] for k in ('seq','phase','flags','raw','tick','temperature_mC','reserved')]
                    values.append(struct.pack(wire.FORMATS[kind],*v))
                data=b''.join(values)
                prefix=self.directory/'exports'/f'{kind}-{first:06d}'
                prefix.parent.mkdir(parents=True,exist_ok=True)
                prefix.with_suffix('.bin').write_bytes(data)
                write_json(prefix.with_suffix('.json'),dict(request_id=100+first,
                    payload_sha256=hashlib.sha256(data).hexdigest(),metadata=dict(**{k:self.phase[k] for k in STRICT},schema=1,record_type=kind,
                    phase_id=1,first=first,count=len(chunk),total=len(rows),record_bytes=struct.calcsize(wire.FORMATS[kind]),
                    next=first+len(chunk),done=first+len(chunk)==len(rows))))
            write_json(self.directory/'exports'/f'{kind}-records.json',rows)
        write_json(self.directory/'exports/rail7-records.json',[r for r in self.rails if r['rail']==7])
        write_json(self.directory/'exports/rail15-records.json',[r for r in self.rails if r['rail']==15])
        write_json(self.directory/'phase.json',self.phase)
        write_json(self.directory/'end-status.json',self.end)
        write_json(self.directory/'start-status.json',self.start)
        write_json(self.directory/'warmup-temperatures.json',self.warm)
        write_json(self.directory/'host-counts.json',self.host)
        (self.directory/'phase-status.jsonl').write_text(json.dumps(dict(host_monotonic=1001,status=self.end))+'\n')
        (self.directory/'frame-events.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in self.frames))


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(analyze,'fail-closed analysis implementation is missing')
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fixture=RawFixture(pathlib.Path(self.temp.name)/'phase with spaces')

    def result(self):
        self.fixture.save()
        return analyze.analyze_phase(self.fixture.directory,synthetic=True)

    def invalid(self,fragment=None):
        result=self.result()
        self.assertFalse(result['valid'])
        self.assertIsNone(result['energy_J'])
        self.assertIsNone(result['mean_W'])
        self.assertIsNone(result['energy_mJ_per_completed_frame'])
        if fragment:self.assertIn(fragment,' '.join(result['invalid_reasons']))
        return result

    def test_diagnostic_hand_fixture_exclusion_and_scope(self):
        f=self.fixture
        f.phase.update(DIAG)
        for s in [f.end,f.start,f.phase['arm_status']]+f.warm:
            s.update(DIAG,conversion_ready_mask=262015,observed_mask=262143,
                     sampler_profile_rails=17,excluded_negative_samples=0)
        f.end['excluded_negative_samples']=33
        f.events=[e for e in f.events if e['type']!=5 or e['request_id']<=200]
        f.end['completed_full']=200
        for r in f.rails:
            r.update(power_uW=2000000,power=64 if r['rail']==10 else 160)
            if r['rail']==7:r.update(flags=258,shunt=65534,power_uW=-(2**63))
        for positive in (False,True):
            if positive:
                for r in f.rails:
                    if r['rail']==7:r.update(flags=3,shunt=1,power=16000,power_uW=200000000)
            f.save()
            result=analyze.analyze_phase(f.directory,True,profile='diagnostic17')
            self.assertTrue(result['valid'],result['invalid_reasons'])
            self.assertEqual((result['energy_J'],result['mean_W'],result['board_completed_fps'],
                              result['energy_mJ_per_completed_frame']),(68.,34.,100.,340.))
            self.assertEqual(result['scope'],'17-rail diagnostic')
            self.assertIsNone(result['rails'][7]['energy_J']);self.assertIsNone(result['rails'][7]['mean_W'])
        out=f.directory.parent/'csv'
        analyze.write_results(out,dict(**DIAG,stages=[result],aggregates=analyze.aggregate([result])))
        for name in ('per-stage.csv','per-repeat.csv'):
            self.assertIn('17-rail diagnostic',(out/name).read_text(encoding='utf-8-sig'))
        for rail,flags in ((7,262),(7,266),(7,274),(7,290),(7,386),(7,259),(6,258)):
            original=f.rails[rail].copy()
            f.rails[rail].update(flags=flags,power_uW=-(2**63),shunt=65534);f.save()
            invalid=analyze.analyze_phase(f.directory,True,profile='diagnostic17')
            self.assertFalse(invalid['valid']);self.assertIsNone(invalid['energy_J'])
            f.rails[rail]=original
        with self.assertRaises(analyze.AnalysisError):analyze.analyze_phase(f.directory,True)

    def test_hand_derived_100ms_linear_integral(self):
        r=analyze.integrate_rail(math_rows(),0,20000,10000)
        self.assertTrue(r['valid'])
        self.assertAlmostEqual(r['energy_J'],6.)
        self.assertAlmostEqual(r['mean_W'],3.)

    def test_cvrf_observed_after_payload_cannot_license_that_payload(self):
        row=self.fixture.rails[18]
        row['begin'][4]=row['end'][3]+1;row['end'][4]=row['end'][3]+2
        self.invalid('CVRF observation occurs after payload')
        result=self.result();rail=result['rails'][0]
        self.assertFalse(rail['valid']);self.assertIsNone(rail['energy_J']);self.assertIsNone(rail['mean_W'])

    def test_host_acceptance_independently_rejects_payload_before_mask(self):
        from host import collect
        row=self.fixture.rails[18];row['end'][4]=row['end'][3]+2
        self.fixture.save()
        with self.assertRaises(collect.GateError):collect.assess_phase(self.fixture.directory)

    def test_raw_18_rails_board_completion_math_and_host_clock_separation(self):
        r=self.result()
        self.assertTrue(r['valid'],r['invalid_reasons'])
        self.assertEqual(r['measurement_origin'],'SYNTHETIC_NOT_PHYSICAL')
        self.assertAlmostEqual(r['energy_J'],108.)
        self.assertAlmostEqual(r['mean_W'],54.)
        self.assertEqual(r['completed_board'],240)
        self.assertEqual(r['board_completed_fps'],120.)
        self.assertAlmostEqual(r['energy_mJ_per_completed_frame'],450.)
        self.assertEqual(r['host']['host_fps'],.5)
        self.assertEqual(r['host']['completed_drain'],239)

    def test_interpolation_uses_bracketing_outside_endpoints(self):
        r=analyze.integrate_rail(math_rows(),500,19500,10000)
        self.assertTrue(r['valid'])
        self.assertAlmostEqual(r['energy_J'],5.7)

    def test_absent_endpoint_is_never_extrapolated(self):
        r=analyze.integrate_rail(math_rows()[1:],0,20000,10000)
        self.assertFalse(r['valid']);self.assertIsNone(r['energy_J'])

    def test_200ms_gap_is_partial_diagnostic_only(self):
        rows=math_rows();del rows[10]
        r=analyze.integrate_rail(rows,0,20000,10000)
        self.assertFalse(r['valid']);self.assertIsNone(r['energy_J'])
        self.assertAlmostEqual(r['partial_coverage_seconds'],1.8)

    def test_missing_rail_invalidates_stage(self):
        self.fixture.rails=[r for r in self.fixture.rails if r['rail']!=17]
        self.invalid()

    def test_invalid_ovf_interrupts_interpolation(self):
        self.fixture.rails[18*16]['flags']=8
        self.fixture.rails[18*16]['power_uW']=-(2**63)
        self.invalid()

    def test_held_reads_do_not_become_independent_updates(self):
        for r in self.fixture.rails:r['flags']=1;r['mask']=0
        self.invalid()

    def test_some_repeated_reads_are_valid_with_recent_cvrf(self):
        rows=math_rows()
        for i,r in enumerate(rows):
            if i%2:r['flags']=1
        r=analyze.integrate_rail(rows,0,20000,10000)
        self.assertFalse(r['valid'])  # observed-update gap200ms exceeds budget.

    def test_held_records_with_100ms_update_observations_are_usable(self):
        rows=[dict(rail=0,flags=3 if i%2==0 else 1,begin=[i*500]*5,end=[i*500]*5,
                   power_uW=3000000,scan_start=i*500) for i in range(41)]
        r=analyze.integrate_rail(rows,0,20000,10000)
        self.assertTrue(r['valid'],r['invalid_reasons'])
        self.assertEqual(r['observed_CVRF'],21)
        self.assertEqual(r['held_reads'],20)
        self.assertAlmostEqual(r['energy_J'],6.)

    def test_backward_read_times_are_not_sorted_away(self):
        r=self.fixture.rails[18*16]
        r['begin']=[70000]*5;r['end']=[70002]*5
        self.invalid()

    def test_duplicate_sequence_is_input_corruption(self):
        self.fixture.save()
        path=self.fixture.directory/'exports/rails-000000.bin'
        data=bytearray(path.read_bytes());struct.pack_into('<I',data,128,0);path.write_bytes(data)
        with self.assertRaises(analyze.AnalysisError):analyze.analyze_phase(self.fixture.directory,synthetic=True)

    def test_duplicate_ack_request_invalidates_stage(self):
        self.fixture.events[3]['request_id']=1
        self.invalid()

    def test_ack_without_host_submission_invalidates_stage(self):
        self.fixture.events[3]['request_id']=999
        self.invalid('submission')

    def test_duplicate_jsonl_key_is_corruption(self):
        self.fixture.save()
        path=self.fixture.directory/'frame-events.jsonl'
        path.write_text('{"event":"produced","event":"missed_slots","count":1}\n')
        with self.assertRaises(analyze.AnalysisError):analyze.analyze_phase(self.fixture.directory,synthetic=True)

    def test_delayed_clock_publication_is_not_a_backwards_completion(self):
        clock=dict(seq=0,phase=1,type=10,request_id=0,mode=0,flags=1,mismatch_count=0,
            reserved=0,begin=79900,end=80100,tick=79950,aux=1)
        self.fixture.events.insert(4,clock)
        r=self.result();self.assertTrue(r['valid'],r['invalid_reasons'])

    def test_invalid_clock_bracket_and_duplicate_clock_sequence_fail(self):
        clock=dict(seq=0,phase=1,type=10,request_id=0,mode=0,flags=1,mismatch_count=0,
            reserved=0,begin=79900,end=80100,tick=79800,aux=1)
        self.fixture.events.insert(4,clock)
        self.invalid('clock')

    def test_backwards_completion_family_is_invalid(self):
        self.fixture.events[4]['tick']=80000
        self.invalid()

    def test_sampler_frequency_mismatch_invalidates_stage(self):
        self.fixture.end['sampler_hz']=7999
        self.invalid()

    def test_out_of_window_acks_are_pre_and_drain_only(self):
        self.fixture.events[2]['tick']=79999
        self.fixture.events[-3]['tick']=96000
        self.fixture.events[1],self.fixture.events[2]=self.fixture.events[2],self.fixture.events[1]
        self.fixture.end['completed_full']=238
        r=self.result()
        self.assertTrue(r['valid'],r['invalid_reasons'])
        self.assertEqual(r['completed_board'],238)
        self.assertEqual(r['drain_board'],1)
        self.assertEqual(r['pre_window_board'],1)

    def test_zero_completion_has_no_per_frame_energy(self):
        self.fixture.events=[e for e in self.fixture.events if e['type']!=5]
        self.fixture.end['completed_full']=0
        r=self.result();self.assertTrue(r['valid'],r['invalid_reasons'])
        self.assertIsNone(r['energy_mJ_per_completed_frame'])

    def test_idle_never_has_per_frame_energy(self):
        self.fixture.events=[e for e in self.fixture.events if e['type']!=5]
        self.fixture.end['completed_full']=0
        for s in [self.fixture.start,self.fixture.end,self.fixture.phase['arm_status']]+self.fixture.warm:s['mode']=0
        for e in self.fixture.events:e['mode']=0
        self.fixture.phase.update(mode=0,fps=None,name='r1-Idle')
        self.fixture.frames=[]
        self.fixture.host.update(produced=0,submitted=0,completed=0,completed_window=0,
            completed_drain=0,host_fps=0,scheduled_slots=0)
        r=self.result();self.assertTrue(r['valid'],r['invalid_reasons'])
        self.assertIsNone(r['energy_mJ_per_completed_frame'])

    def test_sensor_configuration_mismatch(self):
        self.fixture.config[3]['calibration']=1
        self.invalid()

    def test_raw_power_conversion_cannot_be_forged(self):
        self.fixture.rails[18*16]['power_uW']+=1
        self.invalid('conversion')

    def test_buffer_overflow_invalidates_stage(self):
        self.fixture.end['overflows']=1
        self.invalid()

    def test_raw_file_mismatch_is_corruption(self):
        self.fixture.save()
        path=self.fixture.directory/'exports/rails-records.json'
        rows=json.loads(path.read_text());rows[0]['power_uW']=0;write_json(path,rows)
        with self.assertRaises(analyze.AnalysisError):analyze.analyze_phase(self.fixture.directory,synthetic=True)

    def test_thermal_gate_failure_invalidates_stage(self):
        self.fixture.warm[-1]['temperature_mC']=48000
        self.invalid('thermal')

    def test_output_mismatch_even_on_other_event_invalidates_stage(self):
        self.fixture.events[2]['mismatch_count']=1
        self.invalid()

    def test_phase_identity_in_arm_and_markers_must_agree(self):
        self.fixture.phase['board_t0']+=1
        self.invalid()

    def test_host_accounting_cannot_trust_conserved_flag(self):
        self.fixture.host['submitted']=500
        self.invalid('account')

    def test_repetition_aggregation_keeps_invalid_and_sample_sd(self):
        result=self.result();second=copy.deepcopy(result)
        second['mean_W']=56.;second['condition']='Target120-Full';result['condition']='Target120-Full'
        third=copy.deepcopy(result);third.update(valid=False,mean_W=None)
        groups=analyze.aggregate([result,second,third])
        self.assertEqual(groups[0]['repetitions_total'],3)
        self.assertEqual(groups[0]['repetitions_valid'],2)
        self.assertEqual(groups[0]['mean_W']['mean'],55.)
        self.assertAlmostEqual(groups[0]['mean_W']['sample_SD'],2**.5)

    def session(self,policy=STRICT):
        from host import collect
        self.fixture.phase.update(policy)
        for s in [self.fixture.start,self.fixture.end,self.fixture.phase['arm_status']]+self.fixture.warm:
            s.update(policy,conversion_ready_mask=policy['included_mask'],sampler_profile_rails=policy['included_count'])
        self.fixture.save()
        root=self.fixture.directory.parent
        target=root/'phases'/'000-r1-Target120-Full'
        target.parent.mkdir();self.fixture.directory.rename(target)
        self.fixture.directory=target
        identity=json.loads((ROOT/'FIRMWARE_IDENTITY.json').read_text())
        manifest=json.loads((ROOT/'SHA256SUMS.json').read_text())
        if policy==DIAG:
            identity=json.loads((ROOT/'FIRMWARE_IDENTITY_DIAG17.json').read_text())
            manifest=json.loads((ROOT/'SHA256SUMS_DIAG17.json').read_text())
        for e in self.fixture.frames:
            if 'input_sha256' in e:e['input_sha256']=identity['artifact_hashes']['input']
        self.fixture.save()
        plan={k:self.fixture.phase[k] for k in ('name','mode','fps','seconds','scan_ms','offset_ms')}
        session=dict(**policy,schema='e07-host-session-v1',identity=identity,manifest=manifest,status='COMPLETE',
            source_hashes=collect.source_hashes(ROOT),kind='formal',physical=False,peer_ip='127.0.0.1',plan=[dict(plan,**policy)],
            sd_receipt=collect.verify_sd(ROOT,ROOT/('SD_CARD_DIAG17' if policy==DIAG else 'SD_CARD'),root/'receipt.json',policy['measurement_profile']),
            phases=[dict(**policy,path='phases/000-r1-Target120-Full',status='COMPLETE')])
        write_json(root/'session.json',session)
        write_json(root/'startup-status.json',fixture_status(**policy,sampler_profile_rails=policy['included_count']))
        write_json(root/'firmware-identity.json',identity);write_json(root/'manifest.json',manifest)
        write_json(root/'hello.json',dict(**policy,firmware_sha256=identity['firmware_sha256'],artifact_hashes=identity['artifact_hashes'],
            model='E07',phase='E07_INDEPENDENT_CANDIDATE',candidate='E07_INDEPENDENT_POWER_V1',protocol_schema=1,
            physical_status='NOT_RUN',service_cpu='a53-0',sampler_cpu='a53-1',board_ip='192.168.10.2',tcp_port=5001))
        write_json(root/'inventory.json',collect.inventory(root))
        return root,session

    def test_formal_phase_summary_must_match_selected_measurement_profile(self):
        from host import collect
        root,session=self.session(DIAG)
        acceptance=root/'linked acceptance'
        a=self.acceptance_fixture(acceptance,DIAG)
        session.update(physical=True,peer_ip='192.168.10.2',board_id=a['board_id'],controls=a['controls'],
            acceptance_binding=dict(DIAG,path=str(acceptance/'session.json'),sha256=collect.file_hash(acceptance/'session.json'),
                                    inventory_sha256=collect.file_hash(acceptance/'inventory.json')))
        write_json(root/'inventory.json',collect.inventory(root))
        write_json(root/'session.json',session)
        self.assertTrue(analyze.analyze_session(root,profile='diagnostic17')['valid'])
        saved=session['phases'][0]
        for invalid in ([dict(saved,**STRICT)],[],[saved,saved]):
            with self.subTest(summaries=invalid):
                session['phases']=invalid
                write_json(root/'session.json',session)
                with self.assertRaises(analyze.IdentityError):analyze.analyze_session(root,profile='diagnostic17')

    def test_analysis_cli_explicit_diagnostic_session_and_cross_profile_refusal(self):
        root,_=self.session(DIAG)
        out=root.parent/(root.name+' derived diagnostic')
        self.addCleanup(lambda:shutil.rmtree(out,ignore_errors=True))
        args=[sys.executable,'-B','-S',str(ROOT/'host/analyze.py'),str(root),'--synthetic','--output',str(out)]
        strict=subprocess.run(args,capture_output=True,text=True)
        self.assertEqual(strict.returncode,2);self.assertFalse(out.exists())
        result=subprocess.run(args+['--diagnostic17'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        analysis=json.loads((out/'analysis.json').read_text())
        self.assertEqual((analysis['included_count'],analysis['stages'][0]['energy_J']),(17,102.))
    def test_session_simulation_can_never_be_physical_result(self):
        root,_=self.session()
        r=analyze.analyze_session(root)
        self.assertFalse(r['valid'])
        self.assertIsNone(r['stages'][0]['mean_W'])
        for rail in r['stages'][0]['rails']:
            self.assertFalse(rail['valid'])
            for key in ('energy_J','mean_W','energy_mJ_per_completed_frame'):self.assertIsNone(rail[key])
            self.assertGreater(rail['partial_energy_J'],0)

    def test_window_drops_exclude_warmup_and_count_boundary_cohorts(self):
        f=self.fixture
        f.phase['fps']=2
        for sequence,tick in enumerate((999.5,1000.,1002.)):
            frame=dict(stream=3,sequence=sequence,phase=f.phase['name'],input_sha256='a'*64,
                       planned_monotonic=tick,produced_monotonic=tick)
            f.frames.extend([dict(frame,event='produced'),dict(frame,event='evicted',host_monotonic=tick+1)])
        f.frames.append(dict(event='missed_slots',stream=2,first_sequence=0,count=9,phase=f.phase['name'],
                             host_monotonic=1003.5,schedule_start_monotonic=999.))
        f.host.update(produced=243,evicted=3,missed_slots=9,scheduled_slots=252)
        result=self.result()
        self.assertTrue(result['valid'],result['invalid_reasons'])
        self.assertEqual((result['dropped_frames'],result['missed_slots']),(1,4))
        self.assertEqual((result['whole_run_evicted_frames'],result['whole_run_missed_slots']),(3,9))
        self.assertEqual(result['host_window_monotonic'],[1000.,1002.])
        self.assertIsNone(result['board_window_dropped_frames'])

    def test_synthetic_session_outputs_and_csv_are_explicit(self):
        root,_=self.session();r=analyze.analyze_session(root,synthetic=True)
        self.assertTrue(r['valid'],r['stages'][0]['invalid_reasons'])
        out=root.parent/(root.name+' derived')
        self.addCleanup(lambda:__import__('shutil').rmtree(out,ignore_errors=True))
        analyze.write_results(out,r)
        self.assertIn('SYNTHETIC_NOT_PHYSICAL',(out/'per-stage.csv').read_text(encoding='utf-8-sig'))
        self.assertEqual(json.loads((out/'analysis.json').read_text())['stages'][0]['energy_J'],108.)
        self.assertTrue((out/'per-repeat.csv').is_file())
        with self.assertRaises(FileExistsError):analyze.write_results(out,r)

    def test_cross_profile_status_and_formal_binding_abort_before_results(self):
        from host import collect
        root,session=self.session(DIAG)
        directory=self.fixture.directory
        stage=directory/'end-status.json';original=stage.read_bytes()
        write_json(stage,dict(json.loads(original),**STRICT))
        write_json(root/'inventory.json',collect.inventory(root))
        with self.assertRaises(analyze.AnalysisError):
            analyze.analyze_session(root,synthetic=True,profile='diagnostic17')
        stage.write_bytes(original);write_json(root/'inventory.json',collect.inventory(root))
        session.update(physical=True,peer_ip='192.168.10.2',acceptance_binding=dict(STRICT,path='wrong'))
        write_json(root/'session.json',session)
        with self.assertRaises(analyze.AnalysisError):
            analyze.analyze_session(root,profile='diagnostic17')
    def test_wrong_firmware_session_is_rejected_before_output(self):
        root,s=self.session();s['identity']=dict(s['identity'],firmware_sha256='0'*64)
        write_json(root/'session.json',s)
        with self.assertRaises(analyze.AnalysisError):analyze.analyze_session(root,synthetic=True)

    def test_malformed_hello_candidate_cannot_use_matching_hash_only(self):
        from host import collect
        root,_=self.session()
        hello=json.loads((root/'hello.json').read_text());hello['candidate']='legacy'
        write_json(root/'hello.json',hello);write_json(root/'inventory.json',collect.inventory(root))
        with self.assertRaises(analyze.AnalysisError):analyze.analyze_session(root,synthetic=True)

    def test_analysis_cli_supports_relocated_acceptance_argument(self):
        r=subprocess.run([sys.executable,'-S',str(ROOT/'host/analyze.py'),'--help'],text=True,capture_output=True)
        self.assertEqual(r.returncode,0)
        self.assertIn('--acceptance-session',r.stdout)

    def test_raw_inventory_tamper_aborts_session_analysis(self):
        root,_=self.session();(root/'hello.json').write_text('{}')
        with self.assertRaises(analyze.AnalysisError):analyze.analyze_session(root,synthetic=True)

    def test_windows_inventory_spelling_preserves_payload_and_raw_hash(self):
        from host import collect
        root,s=self.session()
        s['phases'][0]['path']='phases\\000-r1-Target120-Full'
        write_json(root/'session.json',s)
        inventory=collect.inventory(root)
        write_json(root/'inventory.json',{str(pathlib.PureWindowsPath(k)):v for k,v in inventory.items()})
        before=(root/'inventory.json').read_bytes()
        raw_hash=collect.file_hash(root/'inventory.json')
        result=analyze.analyze_session(root,synthetic=True)
        self.assertTrue(result['valid'],result['stages'][0]['invalid_reasons'])
        self.assertEqual(result['stages'][0]['energy_J'],108.)
        self.assertEqual(result['stages'][0]['phase_path'],'phases/000-r1-Target120-Full')
        self.assertEqual(result['raw_inventory_sha256'],raw_hash)
        self.assertEqual((root/'inventory.json').read_bytes(),before)
        self.assertTrue(all('\\' not in k for k in result['stages'][0]['raw_hashes']))

    def test_unsafe_or_colliding_inventory_names_are_rejected(self):
        from host import collect
        entry=dict(bytes=1,sha256='0'*64)
        unsafe=['/absolute','\\rooted','C:\\drive','C:relative','\\\\host\\share',
                '../outside','a/../outside','a\\..\\outside','./a','a//b','a\\\\b','a\x00b','']
        self.assertTrue(hasattr(collect,'normalize_inventory'),'portable inventory validation is missing')
        for name in unsafe:
            with self.subTest(name=name),self.assertRaises(collect.GateError):
                collect.normalize_inventory({name:entry})
        with self.assertRaises(collect.GateError):
            collect.normalize_inventory({'a/b':entry,'a\\b':entry})

    def test_future_relative_paths_are_posix_on_windows(self):
        from host import collect
        self.assertTrue(hasattr(collect,'relative_key'),'canonical relative path output is missing')
        self.assertEqual(collect.relative_key(pathlib.PureWindowsPath('D:/raw/phases/000-phase'),
                                            pathlib.PureWindowsPath('D:/raw')),'phases/000-phase')
        self.assertEqual(collect.relative_key(pathlib.PurePosixPath('/raw/exports/rails-000000.bin'),
                                            pathlib.PurePosixPath('/raw')),'exports/rails-000000.bin')

    def test_saved_phase_paths_are_validated_instead_of_ignored(self):
        root,s=self.session()
        s['phases'][0]['path']='..\\outside'
        write_json(root/'session.json',s)
        with self.assertRaises(analyze.AnalysisError):analyze.analyze_session(root,synthetic=True)

    def acceptance_fixture(self,root,policy=STRICT):
        """Synthetic complete collector-gate evidence; never a board result."""
        from host import collect
        identity=json.loads((ROOT/'FIRMWARE_IDENTITY.json').read_text())
        manifest=json.loads((ROOT/'SHA256SUMS.json').read_text())
        if policy==DIAG:
            identity=json.loads((ROOT/'FIRMWARE_IDENTITY_DIAG17.json').read_text())
            manifest=json.loads((ROOT/'SHA256SUMS_DIAG17.json').read_text())
        profile=policy['measurement_profile']
        plan=collect.acceptance_plan(profile);warning_count=0
        for index,p in enumerate(plan):
            f=RawFixture(root/'phases'/f'{index:03d}-{p["name"]}')
            t1=80000+p['seconds']*8000
            template=f.rails[:18];f.rails=[]
            for scan,tick in enumerate(range(72000,t1+8001,1000)):
                for row in template:
                    r=copy.deepcopy(row);r.update(scan=scan,power=96 if r['rail']==10 else 240,
                        power_uW=3000000,begin=[tick-8,tick-6,tick-4,tick-1,tick-10],
                        end=[tick-7,tick-5,tick-3,tick+1,tick-9],scan_start=tick-11)
                    if policy==DIAG and r['rail']==7:r.update(flags=258,shunt=65534,power_uW=-(2**63))
                    f.rails.append(r)
            f.phase.update(p,board_t1=t1)
            for s in [f.start,f.end,f.phase['arm_status']]+f.warm:
                s.update(policy,sampler_profile_rails=policy['included_count'],conversion_ready_mask=policy['included_mask'])
                s.update({k:p[k] for k in ('mode','scan_ms','offset_ms')})
            for s in [*f.warm,f.start,f.phase['arm_status']]:s['excluded_negative_samples']=warning_count
            warning_count+=sum(r['rail']==7 and r['flags']==258 for r in f.rails)
            f.end['excluded_negative_samples']=warning_count
            for s in (f.end,f.phase['arm_status']):
                s.update(t1=t1,now_ticks=t1+8100,sampler_heartbeat=t1+8000,temperature_tick=t1+8000)
            f.events[0]['end']=t1;f.events[-2]['tick']=t1;f.events[-1]['tick']=t1+8001
            for e in f.events:e['mode']=p['mode']
            if p['mode'] in (0,3):
                f.events=[e for e in f.events if e['type']!=5];f.frames=[]
                f.host.update(produced=0,submitted=0,completed=0,completed_window=0,
                              completed_drain=0,host_fps=0,scheduled_slots=0)
            if p['mode'] in (2,3):
                f.events.insert(1,dict(seq=0,phase=1,type=6,request_id=1 if p['mode']==2 else 0,
                    mode=p['mode'],flags=1,mismatch_count=0,reserved=0,
                    begin=72000,end=80000,tick=80000,aux=0))
            f.end.update(completed_full=240 if p['mode']==1 else 0,
                completed_compact=240 if p['mode']==2 else 0,completed_continuous=1 if p['mode']==3 else 0)
            f.temps=[dict(seq=i,phase=1,flags=1,raw=30000,tick=tick,temperature_mC=45000,reserved=0)
                     for i,tick in enumerate(range(72000,t1+8001,8000))]
            for e in f.frames:
                e['phase']=p['name'];e['input_sha256']=identity['artifact_hashes']['input']
                if e['event']=='completed':e['board_response']['mode']='replay_full' if p['mode']==1 else 'replay_compact'
            f.save()
        comparison=[]
        for enabled in (0,1):
            base=160000+enabled*80000;host=10.+enabled*10
            setting=fixture_status(mode=2,sampling_enabled=enabled,ready=bool(enabled),scan_count=10,
                now_ticks=base,sampler_heartbeat=base-1,temperature_tick=base)
            setting.update(policy,conversion_ready_mask=policy['included_mask'],sampler_profile_rails=policy['included_count'])
            observations=[]
            for i in range(3 if not enabled else 1):
                now=base+200*(i+1)
                observed=dict(setting,now_ticks=now,sampler_heartbeat=now-1,scan_count=10+enabled)
                observations.append(dict(host_monotonic=host+.025*(i+1),status=observed))
            (root/f'sampling{enabled}-observations.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in observations))
            start=host+1;end=start+5;rid=100+enabled
            frame=dict(stream=None,sequence=rid,phase='throughput-comparison',
                input_sha256=identity['artifact_hashes']['input'],planned_monotonic=None,produced_monotonic=start+.1)
            response=dict(fixture='E07_FIXED_INPUT',mode='replay_compact',edge_rx_start_ticks=100,
                edge_rx_end_ticks=101,inference_start_ticks=102,inference_end_ticks=103,result_queue_ticks=104,
                timer_frequency_hz=8000,mismatch_count=0,predicted_class=0,total_ticks=1)
            frames=[dict(event='interval_start',host_monotonic=start,sampling_enabled=enabled),
                dict(frame,event='produced'),dict(frame,event='submitted',request_id=rid,submitted_monotonic=start+.2),
                dict(frame,event='completed',request_id=rid,submitted_monotonic=start+.2,
                     received_monotonic=end-.1,verified=True,e2e_seconds=4.8,transaction_seconds=4.7,board_response=response),
                dict(event='interval_end',host_monotonic=end,sampling_enabled=enabled)]
            (root/f'throughput-sampling{enabled}.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in frames))
            comparison.append(dict(**policy,sampling_enabled=enabled,completed=1,failed=0,elapsed_seconds=5,
                interval_monotonic=[start,end],setting_status=setting,observed_status=observations[-1]['status'],
                observation_kind='ready_and_scan_progress' if enabled else 'inferred_off_from_stable_scan_count',
                test_data_kind='SYNTHETIC_NOT_PHYSICAL'))
        controls={k:'SYNTHETIC_FIXTURE' for k in ('cpu_clock','pl_clock','power_supply','fan','network','environment')}
        session=dict(**policy,schema='e07-host-session-v1',manifest=manifest,kind='acceptance',status='COMPLETE',physical=True,
            peer_ip='192.168.10.2',identity=identity,board_id='SYNTHETIC_BOARD_FIXTURE',controls=controls,
            source_hashes=collect.source_hashes(ROOT),plan=plan,sd_receipt=collect.verify_sd(ROOT,ROOT/('SD_CARD_DIAG17' if policy==DIAG else 'SD_CARD'),root/'receipt.json',profile),
            throughput_comparison=comparison)
        from host import wire
        write_json(root/'manifest.json',manifest);write_json(root/'firmware-identity.json',identity)
        write_json(root/'startup-status.json',fixture_status(**policy,conversion_ready_mask=policy['included_mask'],sampler_profile_rails=policy['included_count']))
        write_json(root/'hello.json',wire.expected_greeting(identity))
        write_json(root/'throughput-comparison.json',comparison);write_json(root/'session.json',session)
        write_json(root/'inventory.json',{str(pathlib.PureWindowsPath(k)):v for k,v in collect.inventory(root).items()})
        return session

    def test_reconstructed_acceptance_rejects_phase_clock_and_failed_output(self):
        from host import collect
        root=pathlib.Path(self.temp.name)/'acceptance';session=self.acceptance_fixture(root)
        directory=root/'phases/000-startup-idle'
        p=directory/'phase.json';original=p.read_bytes()
        for case in ('clock','output'):
            with self.subTest(case=case):
                p.write_bytes(original)
                if case=='clock':
                    phase=json.loads(original);phase['arm_status']['sampler_hz']=7999;write_json(p,phase)
                else:
                    e=directory/'exports/events-000000.bin'
                    data=bytearray(e.read_bytes())
                    struct.pack_into('<I',data,24,1)  # ARM mismatch_count outside ACK family.
                    e.write_bytes(data);side=json.loads(e.with_suffix('.json').read_bytes())
                    side['payload_sha256']=__import__('hashlib').sha256(data).hexdigest();write_json(e.with_suffix('.json'),side)
                    decoded=e.parent/'events-records.json';rows=json.loads(decoded.read_bytes());rows[0]['mismatch_count']=1
                    write_json(decoded,rows)
                write_json(root/'inventory.json',collect.inventory(root))
                with self.assertRaises(collect.GateError):
                    collect.validate_acceptance(root/'session.json',session['identity'],session['board_id'],session['controls'])
                p.write_bytes(original)

    def test_replayed_completed_frame_requires_matching_verified_board_response(self):
        from host import collect
        f=self.fixture
        f.frames[2]['board_response']=dict(mode='replay_compact',fixture='E07_FIXED_INPUT',mismatch_count=0)
        f.save()
        with self.assertRaises(collect.GateError):collect.assess_phase(f.directory)
    def test_diagnostic_warning_counter_covers_rows_and_cannot_roll_back(self):
        from host import collect
        f=self.fixture;f.phase.update(DIAG)
        for s in [*f.warm,f.start,f.phase['arm_status'],f.end]:
            s.update(DIAG,conversion_ready_mask=262015,sampler_profile_rails=17,excluded_negative_samples=10)
        for r in f.rails:
            if r['rail']==7:r.update(flags=258,shunt=65534,power_uW=-(2**63))
        for arm,end,expected in ((15,45,True),(15,42,False),(55,45,False)):
            with self.subTest(arm=arm,end=end):
                f.phase['arm_status']['excluded_negative_samples']=arm;f.end['excluded_negative_samples']=end
                f.save()
                if expected:
                    collect.assess_phase(f.directory,'diagnostic17')
                else:
                    with self.assertRaises(collect.GateError):collect.assess_phase(f.directory,'diagnostic17')

    def test_nested_wrong_profile_refuses_formal_analysis_before_output(self):
        from host import collect
        root,session=self.session(DIAG)
        accepts=root/'acceptance';a=self.acceptance_fixture(accepts,DIAG)
        wrong=accepts/'phases/000-startup-idle'/'start-status.json'
        write_json(wrong,dict(json.loads(wrong.read_bytes()),**STRICT))
        write_json(accepts/'inventory.json',collect.inventory(accepts))
        session.update(physical=True,peer_ip='192.168.10.2',board_id=a['board_id'],controls=a['controls'],
            acceptance_binding=dict(DIAG,path=str(accepts/'session.json'),sha256=collect.file_hash(accepts/'session.json'),
                                    inventory_sha256=collect.file_hash(accepts/'inventory.json')))
        write_json(root/'session.json',session);write_json(root/'inventory.json',collect.inventory(root))
        out=root.parent/(root.name+' invalid analysis')
        self.addCleanup(lambda:shutil.rmtree(out,ignore_errors=True))
        result=subprocess.run([sys.executable,'-B','-S',str(ROOT/'host/analyze.py'),str(root),'--diagnostic17','--output',str(out)],
                              capture_output=True,text=True)
        self.assertEqual(result.returncode,2,result.stderr)
        self.assertFalse(out.exists())

    def test_diagnostic_acceptance_requires_matching_replayed_profile(self):
        from host import collect
        root=pathlib.Path(self.temp.name)/'diagnostic synthetic acceptance'
        session=self.acceptance_fixture(root,DIAG);identity=session['identity']
        args=(session['board_id'],session['controls'])
        check=lambda identity:collect.validate_acceptance(root/'session.json',identity,*args)
        self.assertEqual(check(identity)['measurement_profile'],'diagnostic17')
        with self.assertRaises(collect.GateError):check(collect.read_json(ROOT/'FIRMWARE_IDENTITY.json'))
        path=root/'sampling0-observations.jsonl'
        saved=[json.loads(line) for line in path.read_text().splitlines()]
        saved[0]['status'].update(STRICT)
        path.write_text(''.join(json.dumps(r)+'\n' for r in saved))
        write_json(root/'inventory.json',collect.inventory(root))
        with self.assertRaises(collect.GateError):check(identity)
    def test_windows_inventory_relocated_acceptance_keeps_original_binding(self):
        from host import collect
        root,s=self.session()
        acceptance=root/'acceptance original'
        accepted=self.acceptance_fixture(acceptance)
        raw_inventory=(acceptance/'inventory.json').read_bytes()
        binding=dict(**STRICT,path='D:\\old Windows results\\acceptance1\\session.json',
            sha256=collect.file_hash(acceptance/'session.json'),inventory_sha256=collect.file_hash(acceptance/'inventory.json'))
        relocated=root/'relocated acceptance with spaces';shutil.move(str(acceptance),relocated)
        checked=collect.validate_acceptance(relocated/'session.json',accepted['identity'],accepted['board_id'],accepted['controls'])
        self.assertEqual(checked['inventory_sha256'],binding['inventory_sha256'])
        self.assertEqual((relocated/'inventory.json').read_bytes(),raw_inventory)
        s.update(physical=True,peer_ip='192.168.10.2',board_id=accepted['board_id'],controls=accepted['controls'],acceptance_binding=binding)
        write_json(root/'session.json',s)
        write_json(root/'inventory.json',{str(pathlib.PureWindowsPath(k)):v for k,v in collect.inventory(root).items()})
        result=analyze.analyze_session(root,acceptance_session=relocated/'session.json')
        self.assertTrue(result['valid'],result['session_invalid_reasons'])
        self.assertEqual(result['stages'][0]['energy_J'],108.)
        self.assertEqual((relocated/'inventory.json').read_bytes(),raw_inventory)

    def test_acceptance_requires_all_four_raw_toggle_files_even_with_new_inventory(self):
        from host import collect
        root=pathlib.Path(self.temp.name)/'synthetic acceptance';s=self.acceptance_fixture(root)
        for name in ('sampling0-observations.jsonl','sampling1-observations.jsonl',
                     'throughput-sampling0.jsonl','throughput-sampling1.jsonl'):
            with self.subTest(name=name):
                path=root/name;before=path.read_bytes();path.unlink()
                write_json(root/'inventory.json',collect.inventory(root))
                with self.assertRaises(collect.GateError):
                    collect.validate_acceptance(root/'session.json',s['identity'],s['board_id'],s['controls'])
                path.write_bytes(before)

    def test_acceptance_reassesses_toggle_observations_and_frames_after_inventory_recalculation(self):
        from host import collect
        root=pathlib.Path(self.temp.name)/'synthetic acceptance';original=self.acceptance_fixture(root)
        names=['sampling0-observations.jsonl','sampling1-observations.jsonl','throughput-sampling0.jsonl',
               'throughput-sampling1.jsonl','throughput-comparison.json','session.json']
        baseline={name:(root/name).read_bytes() for name in names}
        cases=('off_progress','off_heartbeat','off_host_span','on_scan','on_ready','on_heartbeat',
               'wrong_enable','wrong_mode','wrong_scan','fault','frequency','unverified','output_mismatch',
               'frame_count','duration','raw_interval','empty_frames')
        for case in cases:
            with self.subTest(case=case):
                for name,data in baseline.items():(root/name).write_bytes(data)
                comparison=copy.deepcopy(original['throughput_comparison'])
                enabled=0 if case.startswith('off_') else 1
                obs_path=root/f'sampling{enabled}-observations.jsonl'
                observations=[json.loads(line) for line in obs_path.read_text().splitlines()]
                if case=='off_progress':
                    for i,r in enumerate(observations):r['status']['scan_count']=11+i
                elif case=='off_heartbeat':observations[-1]['status']['sampler_heartbeat']=observations[-2]['status']['sampler_heartbeat']
                elif case=='off_host_span':
                    for i,r in enumerate(observations):r['host_monotonic']=10.001+i*.001
                elif case=='on_scan':observations[-1]['status']['scan_count']=10
                elif case=='on_ready':observations[-1]['status']['ready']=False
                elif case=='on_heartbeat':observations[-1]['status']['sampler_heartbeat']=239999
                elif case=='wrong_enable':observations[-1]['status']['sampling_enabled']=0
                elif case=='wrong_mode':observations[-1]['status']['mode']=1
                elif case=='wrong_scan':observations[-1]['status']['scan_ms']=23
                elif case=='fault':observations[-1]['status']['sampler_faults']=2
                elif case=='frequency':observations[-1]['status']['sampler_hz']=7999
                obs_path.write_text(''.join(json.dumps(r)+'\n' for r in observations))
                comparison[enabled]['observed_status']=observations[-1]['status']
                frames_path=root/'throughput-sampling1.jsonl'
                frames=[json.loads(line) for line in frames_path.read_text().splitlines()]
                if case=='unverified':frames[3]['verified']=False
                elif case=='output_mismatch':frames[3]['board_response']['mismatch_count']=1
                elif case=='frame_count':comparison[1]['completed']=2
                elif case=='duration':comparison[1]['elapsed_seconds']=6
                elif case=='raw_interval':frames[-1]['host_monotonic']-=1
                if case=='empty_frames':frames=[]
                frames_path.write_text(''.join(json.dumps(r)+'\n' for r in frames))
                session=dict(original,throughput_comparison=comparison)
                write_json(root/'session.json',session);write_json(root/'throughput-comparison.json',comparison)
                write_json(root/'inventory.json',collect.inventory(root))
                with self.assertRaises(collect.GateError):
                    collect.validate_acceptance(root/'session.json',session['identity'],session['board_id'],session['controls'])
    def test_analysis_cli_refuses_raw_output_directory(self):
        root,_=self.session()
        r=subprocess.run([sys.executable,'-S',str(ROOT/'host/analyze.py'),str(root),
            '--synthetic','--output',str(root/'derived')],text=True,capture_output=True,cwd='/tmp')
        self.assertEqual(r.returncode,2)
        self.assertFalse((root/'derived').exists())

    def test_analysis_refuses_output_in_immutable_package(self):
        root,_=self.session()
        with tempfile.TemporaryDirectory(prefix='e07 separate package ') as d:
            base=pathlib.Path(d);archive=base/'delivery.zip';package.build_archive(ROOT,archive)
            package_root=base/'extracted'
            with zipfile.ZipFile(archive) as z:z.extractall(package_root)
            with mock.patch.object(analyze,'ROOT',package_root),self.assertRaisesRegex(analyze.AnalysisError,'immutable package'):
                analyze.main([str(root),'--synthetic','--output',str(package_root/'derived')])
            self.assertFalse((package_root/'derived').exists())


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(package,'portable package implementation is missing')

    def test_archive_unique_crc_manifest_relocation_and_tamper(self):
        with tempfile.TemporaryDirectory(prefix='e07 test space ') as d:
            base=pathlib.Path(d);archive=base/'portable candidate.zip'
            info=package.build_archive(ROOT,archive)
            self.assertGreater(info['file_count'],40)
            with zipfile.ZipFile(archive) as z:
                for sd,root_id in [('SD_CARD','FIRMWARE_IDENTITY.json'),('SD_CARD_DIAG17','FIRMWARE_IDENTITY_DIAG17.json')]:
                    self.assertIn(sd+'/BOOT.BIN',z.namelist())
                    identity=json.loads(z.read(root_id))
                    for cpu in ('sampler','service'):self.assertIn(identity['ELF'][cpu]['path'],z.namelist())
                self.assertIn('DIAGNOSTIC17.diff',z.namelist())
            with self.assertRaises(FileExistsError):package.build_archive(ROOT,archive)
            with zipfile.ZipFile(archive) as z:
                self.assertIsNone(z.testzip());z.extractall(base/'extracted package')
            extracted=base/'extracted package'
            verified=package.verify_package(extracted)
            self.assertEqual(verified['file_count'],info['file_count'])
            for args in ([sys.executable,'-S',str(extracted/'package.py'),'--check-only'],
                         [sys.executable,'-S',str(extracted/'host/collect.py'),'--check-only'],
                         [sys.executable,'-S',str(extracted/'host/analyze.py'),'--help']):
                r=subprocess.run(args,text=True,capture_output=True,cwd='/tmp')
                self.assertEqual(r.returncode,0,r.stderr)
            repeated=subprocess.run([sys.executable,'-S',str(extracted/'package.py'),'--check-only'],
                text=True,capture_output=True,cwd='/tmp')
            self.assertEqual(repeated.returncode,0,repeated.stderr)
            self.assertEqual(list(extracted.rglob('*.pyc')),[])
            collector=extracted/'host/collect.py';original=collector.read_bytes()
            marker=base/'unexpected results'
            collector.write_text('import pathlib\npathlib.Path('+repr(str(marker))+').mkdir()\n')
            r=subprocess.run([sys.executable,'-S',str(extracted/'package.py'),'--check-only'],
                text=True,capture_output=True,cwd='/tmp')
            self.assertEqual(r.returncode,2)
            self.assertFalse(marker.exists(),'tampered runtime imported before integrity verification')
            collector.write_bytes(original)
            with (extracted/'SD_CARD/input.bin').open('r+b') as f:f.write(b'bad!')
            r=subprocess.run([sys.executable,'-S',str(extracted/'package.py'),'--check-only'],
                text=True,capture_output=True,cwd='/tmp')
            self.assertEqual(r.returncode,2)
            self.assertEqual(list(extracted.glob('results*')),[])
            rejected=subprocess.run([sys.executable,'-B','-S',str(extracted/'host/collect.py'),'--check-only',
                                     '--diagnostic17'],text=True,capture_output=True)
            self.assertEqual(rejected.returncode,2,rejected.stderr)
            self.assertIn('FAILED:',rejected.stderr)
            self.assertIn('SD_CARD/input.bin',rejected.stderr)

    def test_manifest_cannot_escape_package_or_ignore_added_file(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d)
            write_json(root/'PACKAGE_SHA256SUMS.json',{'../escape':dict(bytes=1,sha256='0'*64)})
            with self.assertRaises(package.PackageError):package.verify_package(root)

    def test_required_python_version_is_enforced(self):
        with self.assertRaises(package.PackageError):package.require_python((3,10,99))
        package.require_python((3,11,0))

    def test_inventory_mismatch_names_extra_files_without_waiving_integrity(self):
        with tempfile.TemporaryDirectory(prefix='e07 inventory diff ') as d:
            base=pathlib.Path(d);archive=base/'delivery.zip'
            package.build_archive(ROOT,archive)
            with zipfile.ZipFile(archive) as z:z.extractall(base/'extracted')
            root=base/'extracted';(root/'controls.json').write_text('{}')
            with self.assertRaises(package.PackageError) as caught:package.verify_package(root)
            self.assertIn('controls.json',str(caught.exception))
            self.assertIn('unexpected',str(caught.exception))

    def test_cache_named_directory_cannot_hide_unmanifested_evidence(self):
        with tempfile.TemporaryDirectory(prefix='e07 strict cache ') as d:
            base=pathlib.Path(d);archive=base/'delivery.zip';package.build_archive(ROOT,archive)
            with zipfile.ZipFile(archive) as z:z.extractall(base/'extracted')
            root=base/'extracted';foreign=root/'host/__pycache__/controls.json'
            foreign.parent.mkdir();foreign.write_text('{}')
            with self.assertRaises(package.PackageError) as caught:package.verify_package(root)
            self.assertIn('host/__pycache__/controls.json',str(caught.exception))


if __name__=='__main__':unittest.main()
