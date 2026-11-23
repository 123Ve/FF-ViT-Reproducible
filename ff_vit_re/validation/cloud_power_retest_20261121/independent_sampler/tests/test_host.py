"""Real TCP I/O doubles; expectations are protocol literals, not client builders."""
import contextlib
import hashlib
import importlib
import json
import pathlib
import socket
import struct
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    wire = importlib.import_module('host.wire')
    load = importlib.import_module('host.load')
    collect = importlib.import_module('host.collect')
except ModuleNotFoundError:
    wire = load = collect = None


STRICT=dict(measurement_profile='strict18',included_mask=262143,included_count=18,excluded_rails=[],
            scope='18 monitored supply rails; not external whole-board input power')
DIAG=dict(measurement_profile='diagnostic17',included_mask=262015,included_count=17,excluded_rails=[7],
          scope='17-rail diagnostic')

def status(**changes):
    value = dict(**STRICT,observed_mask=262143,excluded_negative_samples=0,included_negative_samples=0,sampler_profile_rails=18,schema=1, physical_status='NOT_RUN', ready=True, snapshot_valid=True,
        phase_id=0, state=0, faults=0, sampler_faults=0, service_core=0, sampler_core=1,
        epoch=7, sampler_epoch=7, timer_hz=1000, sampler_hz=1000, now_ticks=10000,
        sampler_heartbeat=9990, clock_checks=4, heartbeat_advances=4, configured_mask=262143,
        configured_tick=1000, conversion_ready_mask=262143,initializing_samples=18,
        mode=2, sampling_enabled=1, scan_ms=20, offset_ms=0,
        t0=0, t1=0, sampler_phase=0, sampler_state=0, rail_records=0, event_records=0,
        temperature_records=0, scan_count=500, completed_full=0, completed_compact=0,
        completed_continuous=0, continuous_begin=0, continuous_end=0, pending_ack=0,
        temperature_mC=45000, temperature_valid=1, temperature_tick=9900,
        i2c_errors=0, invalid_samples=0, stale_samples=0, scan_overruns=0, overflows=0,
        temperature_errors=0)
    value.update(changes)
    return value


def greeting(identity):
    return dict(**(DIAG if identity["measurement_profile"]=="diagnostic17" else STRICT),artifact_hashes=identity['artifact_hashes'], board_ip='192.168.10.2',
        firmware_sha256=identity['firmware_sha256'], model='E07', phase='E07_INDEPENDENT_CANDIDATE',
        tcp_port=5001, candidate='E07_INDEPENDENT_POWER_V1', protocol_schema=1,
        physical_status='NOT_RUN', sampler_cpu='a53-1', service_cpu='a53-0')


def packet(kind, rid, meta, payload=b''):
    meta = json.dumps(meta, separators=(',', ':')).encode()
    return struct.pack('!4sBBHIII', b'FVIT', 1, kind, 0, rid, len(meta), len(payload)) + meta + payload


def readn(sock, n):
    data = b''
    while len(data) < n:
        piece = sock.recv(n-len(data))
        if not piece:
            raise EOFError()
        data += piece
    return data


@contextlib.contextmanager
def server(identity, handler, hello=None):
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen()
    errors = []
    def run():
        try:
            with listener.accept()[0] as sock:
                sock.sendall(packet(5, 0, hello or greeting(identity)))
                while True:
                    try:
                        magic, ver, kind, reserved, rid, nm, np = struct.unpack('!4sBBHIII', readn(sock, 20))
                    except EOFError:
                        break
                    assert (magic, ver, kind, reserved) == (b'FVIT', 1, 7, 0)
                    meta = json.loads(readn(sock, nm))
                    assert set(meta) == {'name', 'arguments'}
                    body = readn(sock, np)
                    reply = handler(meta['name'], meta['arguments'], body, rid)
                    if reply is None:
                        return
                    sock.sendall(reply)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except BaseException as exc:
            errors.append(exc)
    thread = threading.Thread(target=run)
    thread.start()
    sock = socket.create_connection(listener.getsockname(), timeout=1)
    try:
        yield sock
    finally:
        sock.close()
        thread.join(2)
        listener.close()
        if thread.is_alive():
            raise AssertionError('server did not terminate')
        if errors:
            raise errors[0]


class HostTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(wire, 'portable host implementation is missing')
        self.identity = json.loads((ROOT/'FIRMWARE_IDENTITY.json').read_text())

    def test_diagnostic_framing_status_and_wrong_boot(self):
        identity=dict(self.identity,**DIAG)
        hello=dict(greeting(self.identity),**DIAG)
        s=status(**DIAG,conversion_ready_mask=262015,sampler_profile_rails=17,observed_mask=262143,
                 excluded_negative_samples=9)
        with server(identity,lambda n,a,b,r:packet(6,r,s),hello) as sock:
            c=wire.Client(sock,identity)
            collect.validate_status(c.status(),profile='diagnostic17')
            with self.assertRaises(collect.GateError):collect.validate_status(s)
            for changes in (dict(observed_mask=262015),dict(configured_mask=262015),
                            dict(conversion_ready_mask=262014),dict(sampler_profile_rails=18)):
                with self.assertRaises(collect.GateError):
                    collect.validate_status(dict(s,**changes),profile='diagnostic17')
        with server(self.identity,lambda *a:self.fail('request sent'),hello) as sock:
            with self.assertRaises(wire.ProtocolError):wire.Client(sock,self.identity)

    def test_cross_profile_card_receipt_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination=pathlib.Path(tmp)/'receipt.json'
            with self.assertRaises(collect.GateError):
                collect.verify_sd(ROOT,ROOT/'SD_CARD',destination,'diagnostic17')
            collect.verify_sd(ROOT,ROOT/'SD_CARD_DIAG17',destination,'diagnostic17')
            self.assertEqual(collect.validate_receipt(ROOT,destination,'diagnostic17')['included_count'],17)
            with self.assertRaises(collect.GateError):collect.validate_receipt(ROOT,destination)

    def test_configuration_readback_alone_cannot_establish_first_conversion(self):
        with self.assertRaises(collect.GateError):
            collect.validate_status(status(conversion_ready_mask=0,initializing_samples=18))

    def test_result_and_receipt_paths_cannot_pollute_immutable_package(self):
        for option in ('--output','--sd-receipt'):
            with self.subTest(option=option),self.assertRaisesRegex(collect.GateError,'outside'):
                collect.main(['--acceptance',option,str(ROOT/'must-not-create')])
        self.assertFalse((ROOT/'must-not-create').exists())

    def test_startup_waits_for_delayed_healthy_handshake_then_three_advances(self):
        requests=[]
        def handle(name,args,body,rid):
            requests.append(name);n=len(requests);now=10000+100*n
            return packet(6,rid,status(ready=n>=4,clock_checks=min(n,4),heartbeat_advances=min(n,4),
                now_ticks=now,sampler_heartbeat=now-1,temperature_tick=now-1))
        with tempfile.TemporaryDirectory() as tmp,server(self.identity,handle) as sock:
            client=wire.Client(sock,self.identity)
            final=collect.ensure_ready(client,pathlib.Path(tmp))
            self.assertGreaterEqual(len(requests),6)
            self.assertTrue(final['ready'])
            rows=[json.loads(line) for line in (pathlib.Path(tmp)/'readiness-observations.jsonl').read_text().splitlines()]
            self.assertFalse(rows[0]['status']['ready'])
            self.assertGreater(rows[-1]['status']['sampler_heartbeat'],rows[-3]['status']['sampler_heartbeat'])

    def test_startup_never_ready_has_bounded_wait_and_retained_observations(self):
        calls=[]
        def handle(name,args,body,rid):
            calls.append(name)
            return packet(6 if name=='power_status' else 4,rid,status(ready=False,clock_checks=0,
                now_ticks=10000+len(calls)*100,sampler_heartbeat=9999+len(calls)*100))
        with tempfile.TemporaryDirectory() as tmp,server(self.identity,handle) as sock:
            before=time.monotonic()
            with self.assertRaises(collect.GateError):collect.ensure_ready(wire.Client(sock,self.identity),tmp,timeout=.15)
            elapsed=time.monotonic()-before
            self.assertGreaterEqual(elapsed,.14);self.assertLess(elapsed,1)
            self.assertTrue((pathlib.Path(tmp)/'readiness-observations.jsonl').is_file())
            self.assertTrue((pathlib.Path(tmp)/'diagnostics/status.json').is_file())

    def test_startup_fatal_fault_or_wrong_core_does_not_retry_initialization(self):
        for changes in (dict(sampler_faults=2),dict(faults=1),dict(sampler_core=2),dict(sampler_hz=999),dict(sampler_epoch=8)):
            with self.subTest(changes=changes):
                calls=[]
                def handle(name,args,body,rid):
                    calls.append(name)
                    return packet(6 if name=='power_status' else 4,rid,status(ready=False,**changes))
                with tempfile.TemporaryDirectory() as tmp,server(self.identity,handle) as sock:
                    with self.assertRaises(collect.GateError):collect.ensure_ready(wire.Client(sock,self.identity),tmp)
                    self.assertLessEqual(calls.count('power_status'),2)  # first snapshot + diagnostic.
                    self.assertTrue((pathlib.Path(tmp)/'readiness-observations.jsonl').is_file())

    def test_target120_only_formal_profile_preserves_pair_order_and_defaults(self):
        selected=collect.selected_formal_plan(120,5,True)
        self.assertEqual([p['name'] for p in selected], [
            'r1-Target120-Full','r1-Target120-Compact',
            'r2-Target120-Compact','r2-Target120-Full',
            'r3-Target120-Full','r3-Target120-Compact',
            'r4-Target120-Compact','r4-Target120-Full',
            'r5-Target120-Full','r5-Target120-Compact'])
        self.assertTrue(all(p['seconds']==120 and p['fps']==30 for p in selected))
        self.assertEqual(collect.selected_formal_plan(120,5,False),collect.formal_plan())
        # Literal argument array is the PowerShell -Target120Only handoff.
        args=collect.parser().parse_args(['--formal','--target120-only','--seconds','120','--repetitions','5'])
        self.assertTrue(args.formal and args.target120_only)
        self.assertEqual(len(collect.selected_formal_plan(2,1,True)),2)

    def test_target120_only_rejects_nonformal_before_preflight_or_listener(self):
        for action in ('--check-only','--prepare-sd','--acceptance'):
            with self.subTest(action=action),self.assertRaises(collect.GateError):
                collect.main([action,'--target120-only'])

    def test_full_and_compact_actual_socket(self):
        fixture = b'abc'
        def handle(name, args, body, rid):
            if name == 'replay_full':
                return packet(1, rid, self.business(name), body)
            if name == 'replay_compact':
                return packet(2, rid, self.business(name))
            return packet(6, rid, status())
        events = []
        with server(self.identity, handle) as sock:
            c = wire.Client(sock, self.identity, events.append)
            full = c.business('replay_full', fixture)
            compact = c.business('replay_compact', fixture)
        self.assertEqual(full.payload, b'abc')
        self.assertEqual(compact.metadata['mismatch_count'], 0)
        self.assertEqual([x['request_id'] for x in events if x['event']=='request'], [1, 2])
        self.assertTrue(any(x['event']=='response' and x['payload_sha256']==hashlib.sha256(b'abc').hexdigest() for x in events))

    def business(self, mode):
        return dict(fixture='E07_FIXED_INPUT', mode=mode, edge_rx_start_ticks=10,
            edge_rx_end_ticks=11, inference_start_ticks=12, inference_end_ticks=15,
            result_queue_ticks=16, timer_frequency_hz=1000, mismatch_count=0,
            predicted_class=0, total_ticks=3)

    def test_wrong_firmware_refused_before_request(self):
        hello = greeting(self.identity)
        hello['phase'] = 'E07_PHYSICAL'
        with server(self.identity, lambda *a: self.fail('request before identity gate'), hello) as sock:
            with self.assertRaises(wire.ProtocolError):
                wire.Client(sock, self.identity)

    def test_response_corruption_id_kind_compact_verification_and_eof_preserved(self):
        cases = [('payload', 1, b'wrong'), ('kind', 4, b'abc'), ('id', 1, b'abc'),
                 ('mismatch', 2, b''), ('missing_verify', 2, b''), ('eof', 1, b'')]
        for case, kind, payload in cases:
            with self.subTest(case=case):
                def handle(name, args, body, rid):
                    if case == 'eof':
                        return None
                    meta = self.business(name)
                    if case=='mismatch': meta['mismatch_count']=1
                    if case=='missing_verify': del meta['mismatch_count']
                    return packet(kind, rid+1 if case=='id' else rid, meta, payload)
                events=[]
                with server(self.identity, handle) as sock:
                    c=wire.Client(sock,self.identity,events.append)
                    with self.assertRaises((wire.ProtocolError, EOFError)):
                        c.business('replay_compact' if kind==2 else 'replay_full',b'abc')
                self.assertEqual(events[-1]['event'],'error')

    def test_export_phase_and_raw_records(self):
        event=struct.pack('<8I4Q',0,3,5,9,2,1,0,0,100,110,150,200)
        def handle(name,args,body,rid):
            return packet(1,rid,dict(**STRICT,schema=1,record_type='events',phase_id=3,first=0,
                count=1,total=1,record_bytes=64,next=1,done=True),event)
        with tempfile.TemporaryDirectory() as tmp, server(self.identity,handle) as sock:
            c=wire.Client(sock,self.identity)
            rows=c.export('events',pathlib.Path(tmp),3)
            self.assertEqual(rows[0]['tick'],150)
            self.assertEqual((pathlib.Path(tmp)/'events-000000.bin').read_bytes(),event)
            self.assertTrue((pathlib.Path(tmp)/'events-000000.json').exists())

    def test_export_too_early_and_noncontiguous_rejected(self):
        for early in (True,False):
            def handle(name,args,body,rid):
                if early:return packet(255,rid,dict(code='phase_state',detail='DONE only',phase='E07_INDEPENDENT_CANDIDATE'))
                return packet(1,rid,dict(**STRICT,schema=1,record_type='events',phase_id=3,first=1,
                    count=0,total=1,record_bytes=64,next=1,done=True))
            with tempfile.TemporaryDirectory() as tmp,server(self.identity,handle) as sock:
                c=wire.Client(sock,self.identity)
                with self.assertRaises(wire.ProtocolError):c.export('events',pathlib.Path(tmp),3)

    def test_sampler_fault_preserves_negative_latest_and_config_before_arm(self):
        configs=b''.join(struct.pack('<II4HQQ',r,1,0x5449,0x2260,0x4527,2048,1,2) for r in range(18))
        rails=b''.join(struct.pack('<4I8H5Q5QqQ',r,0,2,256 if r==15 else 3,r,0x4527,2048,
            65535 if r==15 else 1,1,65535 if r==15 else 1,1,8,*([1]*5),*([2]*5),
            -(2**63) if r==15 else 12500,1) for r in range(18))
        def handle(name,args,body,rid):
            if name=='power_status':return packet(6,rid,status(ready=False,sampler_faults=2,invalid_samples=1))
            self.assertIn(name,['power_export_config','power_export_latest'])
            typ=name[13:];data=configs if typ=='config' else rails
            return packet(1,rid,dict(**STRICT,schema=1,record_type=typ,phase_id=0,first=0,
                count=18,total=18,record_bytes=32 if typ=='config' else 128,next=18,done=True),data)
        with tempfile.TemporaryDirectory() as tmp,server(self.identity,handle) as sock:
            c=wire.Client(sock,self.identity)
            out=pathlib.Path(tmp)
            with self.assertRaises(collect.GateError):collect.ensure_ready(c,out)
            self.assertEqual(json.loads((out/'diagnostics/latest-records.json').read_text())[15]['flags'],256)
            self.assertTrue((out/'diagnostics/config-000000.bin').exists())
            summary_path=out/'diagnostics/fault-summary.json'
            self.assertTrue(summary_path.is_file())
            summary=json.loads(summary_path.read_text())
            self.assertEqual(len(summary['rails']),18)
            negative=summary['rails'][15]
            self.assertEqual((negative['shunt_raw'],negative['shunt_signed'],negative['shunt_uV']),
                             (65535,-1,-2.5))
            self.assertEqual(negative['current_signed'],-1)
            self.assertEqual(negative['power_uW'],-(2**63))
            self.assertIn('NEGATIVE',negative['reasons'])

    def test_unrelated_diagnostic_does_not_claim_healthy_live_scan_was_frozen(self):
        configs=b''.join(struct.pack('<II4HQQ',r,1,0x5449,0x2260,0x4527,2048,1,2) for r in range(18))
        rails=b''.join(struct.pack('<4I8H5Q5QqQ',r,0,2,3,r,0x4527,2048,1,1,1,1,8,
                                 *([1]*5),*([2]*5),12500,1) for r in range(18))
        def handle(name,args,body,rid):
            if name=='power_status':return packet(6,rid,status())
            typ=name[13:];data=configs if typ=='config' else rails
            return packet(1,rid,dict(**STRICT,schema=1,record_type=typ,phase_id=0,first=0,count=18,total=18,
                record_bytes=32 if typ=='config' else 128,next=18,done=True),data)
        with tempfile.TemporaryDirectory() as tmp,server(self.identity,handle) as sock:
            collect.diagnostics(wire.Client(sock,self.identity),tmp)
            summary=json.loads((pathlib.Path(tmp)/'diagnostics/fault-summary.json').read_text())
            self.assertNotIn('frozen first faulty scan',summary['scan_provenance'])

    def test_invalid_config_refuses_arm(self):
        records=[dict(rail=r,flags=1,manufacturer=0x5449,die=0x2260,config=0x4527,
                      calibration=2048,begin=1,end=2) for r in range(18)]
        collect.validate_config(records)
        records[4]['calibration']=2047
        raw=b''.join(struct.pack('<II4HQQ',*(r[k] for k in
            ('rail','flags','manufacturer','die','config','calibration','begin','end'))) for r in records)
        def handle(name,args,body,rid):
            self.assertEqual(name,'power_export_config')
            return packet(1,rid,dict(**STRICT,schema=1,record_type='config',phase_id=0,first=0,count=18,
                total=18,record_bytes=32,next=18,done=True),raw)
        with tempfile.TemporaryDirectory() as tmp,server(self.identity,handle) as sock:
            c=wire.Client(sock,self.identity)
            with self.assertRaises(collect.GateError):collect.validate_config(c.export('config',tmp))

    def test_package_and_sd_receipt_detect_actual_copy_change(self):
        info=collect.preflight(ROOT)
        self.assertEqual(info['identity']['firmware_sha256'],self.identity['firmware_sha256'])
        with tempfile.TemporaryDirectory() as tmp:
            receipt=pathlib.Path(tmp)/'receipt.json'
            # The delivered SD_CARD is an actual directory to inspect, never a manual pass flag.
            collect.verify_sd(ROOT,ROOT/'SD_CARD',receipt)
            value=collect.validate_receipt(ROOT,receipt)
            self.assertEqual(value['sd_root'],str((ROOT/'SD_CARD').resolve()))
            data=json.loads(receipt.read_text());data['files']['SD_CARD/input.bin']['sha256']='0'*64
            receipt.write_text(json.dumps(data))
            with self.assertRaises(collect.GateError):collect.validate_receipt(ROOT,receipt)

    def test_thermal_deduplicates_cached_ticks_and_requires_fresh_observations(self):
        samples=[status(now_ticks=10000+i*1000,temperature_tick=10000+i*1000) for i in range(31)]
        self.assertTrue(collect.thermal_stable(samples))
        self.assertFalse(collect.thermal_stable([samples[0]]*100))
        self.assertFalse(collect.thermal_stable(samples[:-1]+[status(now_ticks=40000,temperature_tick=1000)]))
        samples[-1]['temperature_mC']=46500
        self.assertFalse(collect.thermal_stable(samples))

    def test_missed_deadline_block_straddles_both_host_window_edges(self):
        events=[]
        q=load.OfferedLoad(2,events.append,phase='slot-test');q.start_at=999.;q.window=(1000.,1002.)
        q.produce_due(0,1003.5)
        self.assertEqual(q.counts()['missed_slots'],9)
        self.assertEqual(q.counts().get('window_missed_slots'),4)
        self.assertEqual(events[0]['schedule_start_monotonic'],999.)
    def test_absolute_deadline_missed_slots_and_oldest_eviction(self):
        events=[]
        q=load.OfferedLoad(10,events.append,clock=lambda:0)
        q.start_at=0
        q.produce_due(0,0)
        q.produce_due(0,.35)
        q.produce_due(0,.4)
        q.produce_due(0,.5)
        # slots .1 and .2 missed; actual frames seq0,3,4,5; seq0 evicted.
        self.assertEqual([f['sequence'] for f in q.queues[0]],[3,4,5])
        self.assertEqual(q.counts()['missed_slots'],2)
        self.assertEqual(q.counts()['produced'],4)
        self.assertEqual(q.counts()['evicted'],1)
        self.assertTrue(q.counts()['conserved'])

    def test_real_producers_continue_while_socket_response_delayed(self):
        def handle(name,args,body,rid):
            time.sleep(.22)
            return packet(1,rid,self.business(name),body)
        q=load.OfferedLoad(30)
        with server(self.identity,handle) as sock:
            c=wire.Client(sock,self.identity)
            q.start()
            try:
                time.sleep(.015)
                f=q.pop()
                q.submit(f,1)
                c.business('replay_full',b'abc')
                q.complete(f,time.monotonic(),True)
            finally:q.stop()
        counts=q.counts()
        self.assertGreaterEqual(counts['produced'],24)
        self.assertGreaterEqual(counts['evicted'],8)
        self.assertEqual(counts['submitted'],1)
        self.assertTrue(counts['conserved'])

    def test_round_robin_drain_window_and_failure_conservation(self):
        q=load.OfferedLoad(10,clock=lambda:0);q.start_at=0
        for stream in range(4):q.produce_due(stream,0)
        q.window=(0,1)
        order=[]
        for i in range(4):
            f=q.pop();order.append(f['stream']);q.submit(f,i+1)
            q.complete(f,.9 if i==0 else 1.1,i!=3)
        self.assertEqual(order,[0,1,2,3])
        c=q.counts();self.assertEqual((c['completed_window'],c['completed_drain'],c['failed']),(1,2,1))
        self.assertTrue(c['conserved'])

    def test_board_completions_use_ack_not_queue_ticks(self):
        events=[dict(type=5,mode=2,flags=1,mismatch_count=0,request_id=1,tick=100),
                dict(type=5,mode=2,flags=1,mismatch_count=0,request_id=2,tick=199),
                dict(type=5,mode=2,flags=1,mismatch_count=0,request_id=3,tick=200)]
        counts=collect.board_counts(events,status(t0=100,t1=200,completed_compact=2),2)
        self.assertEqual(counts,dict(completed_board=2,drain_board=1))

    def test_formal_gate_rejects_manual_flag_and_loopback(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/'session.json'
            p.write_text(json.dumps(dict(status='PASS',physical=True)))
            with self.assertRaises(collect.GateError):collect.validate_acceptance(p,self.identity,'board1',{})
            self.assertFalse(collect.physical_peer('127.0.0.1'))
            self.assertFalse(collect.physical_peer('::1'))
            self.assertTrue(collect.physical_peer('192.168.10.2'))

    def test_window_accounting_excludes_warmup_production_and_measures_e2e(self):
        q=load.OfferedLoad(10,clock=lambda:.4);q.start_at=0;q.window=(.1,.3)
        q.produce_due(0,0);q.produce_due(0,.1);q.produce_due(0,.2)
        f=q.pop();q.submit(f,1);q.complete(f,.5,True)
        counts=q.counts()
        self.assertEqual(counts['window_produced'],2)
        self.assertEqual(counts['window_submitted'],0)
        self.assertEqual(f['e2e_seconds'],.5)
        self.assertEqual(counts['host_fps'],0)

    def exercise_phase(self,wrong_stage=None,interrupt_state=None,stalled=False,reassess=False):
        # Virtualize only collector waits; actual FVIT socket I/O and phase logic run.
        clock=[0.]
        virtual=types.SimpleNamespace(monotonic=lambda:clock[0],sleep=lambda seconds:clock.__setitem__(0,clock[0]+seconds))
        board=dict(phase=0,t0=0,t1=0,done=False,released=False,mode=2,scan_ms=20,offset_ms=0,sampling_enabled=1)
        commands=[]
        def current(mutate=True):
            now=int(clock[0]*1000)+10000
            active=board['phase'] and not board['released']
            state=0 if not active else 1 if now<board['t0'] else 2 if now<board['t1'] else 3
            sampler_state=4 if active and now>=board['t1']+1000 else state
            value=status(now_ticks=now,sampler_heartbeat=now-1,temperature_tick=(now//1000)*1000,
                phase_id=board['phase'],sampler_phase=board['phase'],state=4 if board['done'] else state,
                sampler_state=sampler_state,t0=board['t0'],t1=board['t1'],
                **{k:board[k] for k in ('mode','scan_ms','offset_ms','sampling_enabled')})
            if board['done'] and not board['released']:
                value.update(rail_records=18*len(range(board['t0']-1020,board['t1']+981,20)),
                             event_records=4,temperature_records=1)
            if stalled and active:value['sampler_heartbeat']=board['t0']-1250
            if mutate and wrong_stage and ((wrong_stage[0]=='prearm' and not active) or
                                (wrong_stage[0]=='during' and active and not board['done']) or
                                (wrong_stage[0]=='end' and board['done'])):
                value[wrong_stage[1]]=wrong_stage[2]
            return value
        configs=b''.join(struct.pack('<II4HQQ',r,1,0x5449,0x2260,0x4527,2048,1,2) for r in range(18))
        def handle(name,args,body,rid):
            commands.append(name)
            if name=='power_status':return packet(6,rid,current())
            setting={'power_load':'mode','power_scan':'scan_ms','power_offset':'offset_ms','power_sampling':'sampling_enabled'}
            if name in setting:board[setting[name]]=args['count']
            if name=='power_arm':
                board.update(phase=1,t0=int(clock[0]*1000)+11250,t1=int(clock[0]*1000)+12250)
                if wrong_stage and wrong_stage[0]=='arm':
                    value=current();value[wrong_stage[1]]=wrong_stage[2]
                    return packet(4,rid,value)
                return packet(4,rid,current(mutate=False))
            if name=='power_finish':board['done']=True
            if name=='power_release':board['released']=True
            if name.startswith('power_export_'):
                typ=name[13:]
                if typ=='config':data=configs
                elif typ=='events':
                    data=b''.join(struct.pack('<8I4Q',i,1,t,0,0,0,0,0,board['t0'] if t==1 else 0,
                        board['t1'] if t==1 else 0,tick,0)
                        for i,(t,tick) in enumerate([(1,board['t0']-1250),(2,board['t0']),(3,board['t1']),(4,board['t1']+1000)]))
                elif typ=='temperatures':
                    data=struct.pack('<4IQiI',0,1,1,30000,board['t0'],45000,0)
                else:
                    records=[]
                    # Scheduled postguard ends at +1000ms; last scan is at +980ms.
                    base=board['t0'] or 2000
                    stop=board['t1']+981 if board['t1'] else base+20
                    for tick in range(base-1020,stop,20):
                        for rail in range(18):
                            records.append(struct.pack('<4I8H5Q5QqQ',len(records),1,(tick-board['t0']+1100)//20,3,
                                rail,0x4527,2048,1,1,1,1,8,
                                tick-6,tick-4,tick-2,tick,tick-8,
                                tick-5,tick-3,tick-1,tick+1,tick-7,31250 if rail==10 else 12500,tick-9))
                    data=b''.join(records)
                size=struct.calcsize(wire.FORMATS[typ]);total=len(data)//size;first=args['count']
                count=min(256,total-first)
                return packet(1,rid,dict(**STRICT,schema=1,record_type=typ,phase_id=board['phase'],first=first,
                    count=count,total=total,record_bytes=size,next=first+count,done=first+count==total),data[first*size:(first+count)*size])
            return packet(4,rid,current())
        with tempfile.TemporaryDirectory() as tmp,server(self.identity,handle) as sock:
            client=wire.Client(sock,self.identity)
            runner=collect.Runner(client,pathlib.Path(tmp),b'abc','fixturehash')
            directory=pathlib.Path(tmp)/'phases/000-idle'
            original_status=client.status
            interrupted=[False]
            def observed_status():
                value=original_status()
                if interrupt_state==value['state'] and not interrupted[0]:
                    interrupted[0]=True
                    raise KeyboardInterrupt('operator interrupt')
                return value
            client.status=observed_status
            with mock.patch.object(collect,'time',virtual):
                if wrong_stage or interrupt_state:
                    with self.assertRaises(KeyboardInterrupt if interrupt_state else collect.GateError):
                        runner.phase(0,dict(**STRICT,name='idle',mode=0,fps=None,seconds=1,scan_ms=20,offset_ms=0))
                    if wrong_stage and wrong_stage[0]=='prearm':self.assertNotIn('power_arm',commands)
                    if interrupt_state:
                        self.assertNotIn('power_release',commands)
                        recovery=json.loads((directory/'recovery-result.json').read_text())
                        self.assertEqual(recovery['status'],'INCOMPLETE' if stalled else 'EXPORTED')
                        if stalled:self.assertTrue(recovery['error'])
                        else:
                            self.assertIn('power_finish',commands)
                            self.assertTrue((directory/'recovery-exports/rails-records.json').exists())
                            self.assertGreaterEqual(recovery['final_status']['now_ticks'],board['t1']+1000)
                    return
                result=runner.phase(0,dict(**STRICT,name='idle',mode=0,fps=None,seconds=1,scan_ms=20,offset_ms=0))
            self.assertEqual(result['status'],'COMPLETE')
            self.assertLess(commands.index('power_finish'),commands.index('power_export_rails'))
            self.assertLess(commands.index('power_export_temperatures'),commands.index('power_release'))
            self.assertEqual(len(result['coverage']),18)
            if reassess:
                for location in ('start-status.json','end-status.json','arm_status','phase-status.jsonl','warmup-temperatures.json'):
                    for key,bad in (('mode',2),('scan_ms',23),('offset_ms',5),('sampling_enabled',0)):
                        path=directory/('phase.json' if location=='arm_status' else location)
                        original=path.read_text()
                        if location=='phase-status.jsonl':
                            rows=[json.loads(line) for line in original.splitlines()]
                            rows[0]['status'][key]=bad
                            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
                        else:
                            value=json.loads(original)
                            (value['arm_status'] if location=='arm_status' else value[0] if location=='warmup-temperatures.json' else value)[key]=bad
                            path.write_text(json.dumps(value))
                        with self.assertRaises(collect.GateError):collect.assess_phase(directory)
                        path.write_text(original)

    def test_full_phase_socket_sequence_freezes_exports_then_releases(self):
        self.exercise_phase()

    def test_actual_settings_must_match_plan_before_arm_and_on_arm_during_end(self):
        for stage in ('prearm','arm','during','end'):
            for key,bad in (('mode',2),('scan_ms',23),('offset_ms',5),('sampling_enabled',0)):
                with self.subTest(stage=stage,key=key):self.exercise_phase(wrong_stage=(stage,key,bad))

    def test_acceptance_reassessment_rejects_changed_actual_configuration(self):
        self.exercise_phase(reassess=True)

    def test_interrupt_guard_active_post_recovers_board_records_without_release(self):
        for state in (1,2,3):
            with self.subTest(state=state):self.exercise_phase(interrupt_state=state)

    def test_stopped_sampler_recovery_is_explicitly_incomplete(self):
        self.exercise_phase(interrupt_state=1,stalled=True)

    def test_sampling_toggle_waits_for_observed_scans_and_records_observation(self):
        clock=[0.]
        virtual=types.SimpleNamespace(monotonic=lambda:clock[0],sleep=lambda s:clock.__setitem__(0,clock[0]+s))
        board=dict(enabled=1,changed=0.,last_count=100)
        def handle(name,args,body,rid):
            if name=='power_sampling':
                board.update(enabled=args['count'],changed=clock[0])
            if name=='replay_compact':
                # Fail if the collector starts the interval before the sampler
                # publishes the setting (the desired flag alone is immediate).
                self.assertGreaterEqual(clock[0]-board['changed'],.15)
                clock[0]+=.25
                return packet(2,rid,self.business(name))
            elapsed=clock[0]-board['changed']
            observed=board['enabled'] if elapsed>=.15 else 1-board['enabled']
            count=100+int(clock[0]*50) if observed else board['last_count']
            if observed:board['last_count']=count
            now=10000+int(clock[0]*1000)
            value=status(now_ticks=now,sampler_heartbeat=now-1,temperature_tick=now,
                ready=bool(observed and board['enabled']),sampling_enabled=board['enabled'],scan_count=count)
            return packet(6 if name=='power_status' else 4,rid,value)
        with tempfile.TemporaryDirectory() as tmp,server(self.identity,handle) as sock:
            runner=collect.Runner(wire.Client(sock,self.identity),tmp,b'abc','fixturehash')
            with mock.patch.object(collect,'time',virtual),mock.patch.object(wire,'time',virtual):
                results=runner.comparison()
            collect.validate_toggle_evidence(tmp,results,'fixturehash')
            self.assertEqual([r['observed_status']['sampling_enabled'] for r in results],[0,1])
            self.assertTrue(all(r['observed_status']['sampler_heartbeat']>r['setting_status']['now_ticks'] for r in results))
            self.assertEqual(results[0]['observation_kind'],'inferred_off_from_stable_scan_count')

    def test_sampling_observation_rejects_stale_heartbeat_and_bounded_nonacknowledgement(self):
        for scenario in ('heartbeat','keeps_scanning'):
            with self.subTest(scenario=scenario):
                clock=[0.]
                virtual=types.SimpleNamespace(monotonic=lambda:clock[0],sleep=lambda s:clock.__setitem__(0,clock[0]+s))
                def handle(name,args,body,rid):
                    now=10000+int(clock[0]*1000)
                    return packet(6,rid,status(ready=False,sampling_enabled=0,now_ticks=now,
                        sampler_heartbeat=9900 if scenario=='heartbeat' else now-1,
                        scan_count=100+int(clock[0]*50) if scenario=='keeps_scanning' else 100))
                with tempfile.TemporaryDirectory() as tmp,server(self.identity,handle) as sock:
                    client=wire.Client(sock,self.identity)
                    with mock.patch.object(collect,'time',virtual):
                        with self.assertRaises(collect.GateError):
                            collect.wait_sampling_observed(client,status(sampling_enabled=0),0,pathlib.Path(tmp),timeout=.4)
                    self.assertLess(clock[0],1)

    def test_recovery_unavailable_transport_or_never_done_is_retained_and_bounded(self):
        for scenario in ('eof','never_done'):
            with self.subTest(scenario=scenario):
                clock=[0.];commands=[]
                virtual=types.SimpleNamespace(monotonic=lambda:clock[0],sleep=lambda s:clock.__setitem__(0,clock[0]+s))
                arm=status(phase_id=1,t0=10250,t1=11250)
                def handle(name,args,body,rid):
                    commands.append(name)
                    if scenario=='eof':return None
                    now=10000+int(clock[0]*1000)
                    return packet(6,rid,status(phase_id=1,t0=10250,t1=11250,state=3,sampler_state=3,
                        now_ticks=now,sampler_heartbeat=now-1))
                with tempfile.TemporaryDirectory() as tmp,server(self.identity,handle) as sock:
                    runner=collect.Runner(wire.Client(sock,self.identity),tmp,b'abc','fixturehash')
                    with mock.patch.object(collect,'time',virtual):result=runner.recover(pathlib.Path(tmp),arm)
                    self.assertEqual(result['status'],'INCOMPLETE')
                    self.assertTrue(result['error'])
                    self.assertLess(clock[0],8)
                    self.assertNotIn('power_release',commands)
                    self.assertTrue((pathlib.Path(tmp)/'recovery-result.json').exists())

    def test_control_payload_and_bounds_rejected_raw_bytes_retained(self):
        for scenario in ('control_payload','oversize'):
            def handle(name,args,body,rid):
                if scenario=='oversize':return struct.pack('!4sBBHIII',b'FVIT',1,6,0,rid,65537,0)
                return packet(6,rid,status(),b'bad')
            with tempfile.TemporaryDirectory() as tmp,server(self.identity,handle) as sock:
                client=wire.Client(sock,self.identity,raw_dir=tmp)
                with self.assertRaises(wire.ProtocolError):client.status()
                raw=(pathlib.Path(tmp)/'00000002.fvit').read_bytes()
                self.assertTrue(raw.startswith(b'FVIT'))

    def test_failure_timeout_is_separate_from_remaining_and_window_counts(self):
        q=load.OfferedLoad(10,clock=lambda:0);q.start_at=0
        q.produce_due(0,0);q.produce_due(1,0)
        f=q.pop();q.submit(f,1);q.complete(f,.5,False,'timed out',failure_type='TimeoutError')
        c=q.counts()
        self.assertEqual((c['timeouts'],c['failed'],c['remaining']),(1,1,1))
        self.assertEqual(c['scheduled_slots'],c['missed_slots']+c['produced'])
        self.assertTrue(c['conserved'])

    def test_plans_include_full_acceptance_and_alternate_paired_formal_order(self):
        self.assertTrue(any(p['mode']==1 for p in collect.acceptance_plan()))
        plan=collect.formal_plan()
        self.assertEqual(len(plan),40)
        self.assertEqual([(p['mode'],p['fps']) for p in plan[1:3]],[(1,10),(2,10)])
        self.assertEqual([(p['mode'],p['fps']) for p in plan[9:11]],[(2,10),(1,10)])
        scans=[p for p in collect.acceptance_plan() if p['scan_ms'] in (17,23)]
        self.assertEqual(len(scans),8)
        self.assertTrue(all(p['seconds']==60 for p in scans))


if __name__=='__main__':unittest.main()
