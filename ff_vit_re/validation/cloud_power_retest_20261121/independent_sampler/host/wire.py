"""FVIT schema 1 transport. The calling thread exclusively owns the socket.

FVIT defines no wire CRC: TCP transport plus exact Full equality, Compact
firmware mismatch_count and SHA-256 of every persisted chunk are the available
integrity evidence. Local hashes do not authenticate a malicious peer.
"""
from . import profiles
import dataclasses
import hashlib
import json
import pathlib
import socket
import struct
import threading
import time

HEADER = struct.Struct('!4sBBHIII')
FORMATS = {'rails': '<4I8H5Q5QqQ', 'latest': '<4I8H5Q5QqQ',
           'events': '<8I4Q', 'temperatures': '<4IQiI', 'config': '<II4HQQ'}


class ProtocolError(RuntimeError):
    pass


class BoardError(ProtocolError):
    def __init__(self, metadata):
        self.metadata = metadata
        super().__init__(str(metadata))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save_json(path, value):
    """Exclusive creation prevents silent replacement of primary evidence."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def decode_records(kind, payload):
    layout = struct.Struct(FORMATS[kind])
    if len(payload) % layout.size:
        raise ProtocolError('partial binary record')
    rows = []
    for values in layout.iter_unpack(payload):
        if kind in ('rails', 'latest'):
            names = ['seq', 'phase', 'scan', 'flags', 'rail', 'config', 'calibration',
                     'shunt', 'bus', 'current', 'power', 'mask']
            row = dict(zip(names, values[:12]))
            row.update(begin=list(values[12:17]), end=list(values[17:22]),
                       power_uW=values[22], scan_start=values[23])
        elif kind == 'config':
            row = dict(zip(['rail','flags','manufacturer','die','config','calibration','begin','end'], values))
        elif kind == 'events':
            row = dict(zip(['seq','phase','type','request_id','mode','flags','mismatch_count',
                            'reserved','begin','end','tick','aux'], values))
        else:
            row = dict(zip(['seq','phase','flags','raw','tick','temperature_mC','reserved'], values))
        rows.append(row)
    return rows


@dataclasses.dataclass
class Response:
    kind: int
    request_id: int
    metadata: dict
    payload: bytes
    received_monotonic: float


def validate_business_metadata(m,mode,hz=None):
    fields=('edge_rx_start_ticks','edge_rx_end_ticks','inference_start_ticks','inference_end_ticks',
            'result_queue_ticks','timer_frequency_hz','mismatch_count','predicted_class','total_ticks')
    if not isinstance(m,dict) or any(type(m.get(k)) is not int or m[k]<0 for k in fields):
        raise ProtocolError('missing/invalid business verification or timing data')
    if (m.get('fixture')!='E07_FIXED_INPUT' or m.get('mode')!=mode or m['mismatch_count']!=0 or
        m['timer_frequency_hz']<=0 or (hz is not None and m['timer_frequency_hz']!=hz) or
        not m['edge_rx_start_ticks']<=m['edge_rx_end_ticks']<=m['inference_start_ticks']<=m['inference_end_ticks']<=m['result_queue_ticks']):
        raise ProtocolError('business output reference or clock verification failed')


def expected_greeting(identity):
    return dict(**profiles.metadata(identity['measurement_profile']),model='E07',phase='E07_INDEPENDENT_CANDIDATE',
                candidate='E07_INDEPENDENT_POWER_V1',protocol_schema=1,physical_status='NOT_RUN',
                service_cpu='a53-0',sampler_cpu='a53-1',firmware_sha256=identity['firmware_sha256'],
                artifact_hashes=identity['artifact_hashes'],board_ip='192.168.10.2',tcp_port=5001)


class Client:
    def __init__(self, sock, identity, record=None, raw_dir=None):
        self.profile = identity['measurement_profile']
        self.sock = sock
        self.owner = threading.get_ident()
        self.record = record or (lambda event: None)
        self.raw_dir = pathlib.Path(raw_dir) if raw_dir else None
        if self.raw_dir:self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.next_id = 1
        self.serial = 0
        self.hello = self._receive()
        try:
            h = self.hello
            expected = expected_greeting(identity)
            if h.kind != 5 or h.request_id != 0 or h.payload or h.metadata != expected:
                raise ProtocolError('wrong/legacy firmware greeting or manifest identity')
        except Exception as exc:
            self.record(dict(event='error', operation='hello', detail=str(exc)))
            raise

    def _read(self, n, pieces):
        data = bytearray()
        while len(data) < n:
            part = self.sock.recv(n-len(data))
            if not part:raise EOFError(f'truncated FVIT response: {len(data)}/{n}')
            data.extend(part)
            pieces.append(part)
        return bytes(data)

    def _receive(self):
        pieces=[]
        self.serial += 1
        try:
            header=self._read(20,pieces)
            magic,version,kind,reserved,rid,nm,np=HEADER.unpack(header)
            if (magic,version,reserved)!=(b'FVIT',1,0) or nm>65536 or np>4194304:
                raise ProtocolError('invalid FVIT header/bounds')
            meta_bytes=self._read(nm,pieces)
            body=self._read(np,pieces)
            def pairs(items):
                result={}
                for key,value in items:
                    if key in result:raise ProtocolError('duplicate JSON key')
                    result[key]=value
                return result
            meta=json.loads(meta_bytes.decode('utf-8'), object_pairs_hook=pairs,
                            parse_constant=lambda x: (_ for _ in ()).throw(ProtocolError('nonfinite JSON')))
            if not isinstance(meta,dict):raise ProtocolError('metadata is not object')
            r=Response(kind,rid,meta,body,time.monotonic())
            self.record(dict(event='response',request_id=rid,kind=kind,metadata=meta,
                payload_bytes=len(body),payload_sha256=digest(body),host_monotonic=r.received_monotonic))
            return r
        finally:
            if self.raw_dir:
                data=b''.join(pieces)
                path=self.raw_dir/f'{self.serial:08d}.fvit'
                with path.open('xb') as f:f.write(data)
                save_json(path.with_suffix('.json'),dict(bytes=len(data),sha256=digest(data)))

    def request(self, name, count=None, payload=b'', expected=4):
        if threading.get_ident()!=self.owner:raise RuntimeError('socket belongs to another thread')
        rid=self.next_id
        if rid>0xffffffff:raise ProtocolError('request ID space exhausted')
        self.next_id+=1
        arguments={} if count is None else {'count':count}
        meta=json.dumps(dict(name=name,arguments=arguments),separators=(',',':')).encode()
        if len(payload)>4194304:raise ProtocolError('request payload too large')
        self.record(dict(event='request',request_id=rid,name=name,arguments=arguments,
                         payload_sha256=digest(payload),payload_bytes=len(payload),host_monotonic=time.monotonic()))
        try:
            self.sock.sendall(HEADER.pack(b'FVIT',1,7,0,rid,len(meta),len(payload))+meta+payload)
            r=self._receive()
            if r.request_id!=rid:raise ProtocolError('response request ID mismatch')
            if r.kind==255:raise BoardError(r.metadata)
            if r.kind!=expected:raise ProtocolError('response kind mismatch')
            if expected in (4,6) and name.startswith('power_') and not profiles.matches(r.metadata,self.profile):
                raise ProtocolError('control/status measurement profile mismatch')
            if expected in (4,6) and r.payload:raise ProtocolError('unexpected control/status payload')
            return r
        except Exception as exc:
            self.record(dict(event='error',request_id=rid,name=name,type=type(exc).__name__,detail=str(exc)))
            raise

    def status(self):
        return self.request('power_status',expected=6).metadata

    def business(self, mode, fixture):
        try:
            r=self.request(mode,payload=fixture,expected=1 if mode=='replay_full' else 2)
            m=r.metadata
            validate_business_metadata(m,mode)
            if mode=='replay_full' and r.payload!=fixture:
                raise ProtocolError('Full payload differs from fixed input')
            if mode=='replay_compact' and (r.payload or m['inference_end_ticks']<m['inference_start_ticks']):
                raise ProtocolError('invalid Compact response')
            return r
        except Exception as exc:
            self.record(dict(event='error',operation=mode,type=type(exc).__name__,detail=str(exc)))
            raise

    def export(self, kind, destination, phase=None):
        destination=pathlib.Path(destination)
        destination.mkdir(parents=True,exist_ok=True)
        first=0; total=None; rows=[]; export_phase=phase
        while True:
            for attempt in range(20):
                try:
                    r=self.request('power_export_'+kind,first,expected=1)
                    break
                except BoardError as exc:
                    if exc.metadata.get('code')!='snapshot_busy' or attempt==19:raise
                    time.sleep(.02)
            m=r.metadata
            # Save the untrusted chunk before validation, so malformed replies survive.
            prefix=destination/f'{kind}-{first:06d}'
            with prefix.with_suffix('.bin').open('xb') as f:f.write(r.payload)
            save_json(prefix.with_suffix('.json'),dict(metadata=m,payload_sha256=digest(r.payload),
                                                       request_id=r.request_id))
            size=struct.calcsize(FORMATS[kind])
            if export_phase is None:export_phase=m.get('phase_id')
            if total is None:total=m.get('total')
            if (not profiles.matches(m,self.profile) or m.get('schema')!=1 or m.get('record_type')!=kind or m.get('phase_id')!=export_phase or
                type(total) is not int or total<0 or m.get('total')!=total or m.get('first')!=first or
                m.get('record_bytes')!=size or m.get('count')!=min(256,total-first) or
                m.get('next')!=first+m.get('count',-1) or type(m.get('done')) is not bool or
                m['done']!=(m['next']==total) or len(r.payload)!=m['count']*size):
                raise ProtocolError('invalid/noncontiguous export metadata/payload')
            chunk=decode_records(kind,r.payload)
            for i,row in enumerate(chunk):
                if kind=='config':
                    if row['rail']!=first+i:raise ProtocolError('configuration rail ordering')
                else:
                    if row['seq']!=first+i:raise ProtocolError('record sequence gap/duplicate')
                    if kind!='latest' and row['phase']!=export_phase:raise ProtocolError('record phase mismatch')
            rows.extend(chunk)
            if m['done']:break
            if m['next']<=first:raise ProtocolError('export made no progress')
            first=m['next']
        if kind in ('config','latest') and len(rows)!=18:raise ProtocolError('missing diagnostic/config rails')
        save_json(destination/f'{kind}-records.json',rows)
        if kind=='rails':
            for rail in (7,15):save_json(destination/f'rail{rail}-records.json',[r for r in rows if r['rail']==rail])
        return rows
