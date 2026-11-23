"""Cached Compact requests and bounded, asynchronous JSONL evidence writes."""
import json
import queue
import threading
import time

from Cloud_test.iot_eval.protocol import HEADER, MAX_PAYLOAD_BYTES, read_message
from Cloud_test.run_e07_measurements import SocketStream, validate_response


class TransactionError(OSError):
    def __init__(self, message, diagnostic):
        super().__init__(message)
        self.diagnostic = diagnostic


class ReplayTransport:
    """Single-owner transport; no concurrent requests or changed wire protocol."""
    def __init__(self, connection, payload, request_id=0):
        if not payload or len(payload) > MAX_PAYLOAD_BYTES:
            raise ValueError('invalid replay payload length')
        self.connection = connection
        self.reader = SocketStream(connection)
        self.payload = payload
        self.request_id = request_id
        self.metadata = b'{"arguments":{},"name":"replay_compact"}'
        self.packet = bytearray(HEADER.size + len(self.metadata) + len(payload))
        self.packet[HEADER.size:HEADER.size + len(self.metadata)] = self.metadata
        self.packet[HEADER.size + len(self.metadata):] = payload

    def infer(self, frame):
        self.request_id += 1
        if self.request_id > 0xffffffff:
            raise ValueError('FVIT request ID exhausted; start a new run')
        HEADER.pack_into(self.packet, 0, b'FVIT', 1, 7, 0, self.request_id,
                         len(self.metadata), len(self.payload))
        event = dict(request_id=self.request_id, send_monotonic_ns=time.monotonic_ns(),
                     send_wall_ns=time.time_ns(), socket_sent_bytes=0)
        before = self.reader.bytes_received
        self.reader.begin_message()
        if frame.deadline_ns is not None:
            deadline = frame.deadline_ns / 1e9
            self.reader.deadline = min(self.reader.deadline, deadline) if self.reader.deadline else deadline
        try:
            self.reader.apply_deadline()
            self.connection.sendall(self.packet)
            event['socket_sent_bytes'] = len(self.packet)
            event['source_send_complete_monotonic_ns'] = time.monotonic_ns()
            response = read_message(self.reader)
            event.update(receive_monotonic_ns=time.monotonic_ns(), receive_wall_ns=time.time_ns(),
                         socket_received_bytes=self.reader.bytes_received - before,
                         metadata=response.metadata)
            if response.request_id != self.request_id or response.kind == 'error':
                raise ValueError('Compact response ID or kind mismatch')
            validate_response('replay_compact', response, self.payload, event)
            return event
        except (OSError, ValueError, KeyError, TypeError) as exc:
            event.update(kind='transaction_failure', failure=str(exc), failure_type=type(exc).__name__,
                         failed_monotonic_ns=time.monotonic_ns(),
                         socket_received_bytes=self.reader.bytes_received - before,
                         **self.reader.progress(self.reader.bytes_received - before))
            raise TransactionError(str(exc), event) from exc


class EvidenceWriter:
    """Fail capture on disk errors or queue overflow, never drop evidence silently."""
    def __init__(self, path, capacity=4096, exclusive=True):
        self.stream = path.open('x' if exclusive else 'w', encoding='utf-8', buffering=65536)
        self.queue = queue.Queue(maxsize=capacity)
        self.error = None
        self.closed = False
        self.thread = threading.Thread(target=self._write, name='e07-evidence-writer')
        self.thread.start()

    def emit(self, event):
        if self.error:
            raise OSError('evidence writer failed: ' + str(self.error)) from self.error
        if self.closed:
            raise OSError('evidence writer is closed')
        try:
            self.queue.put_nowait(dict(event))
        except queue.Full as exc:
            raise OSError('evidence queue overflow; capture cannot be considered complete') from exc

    def _write(self):
        try:
            done = False
            while not done:
                item = self.queue.get()
                batch = []
                for index in range(128):
                    if item is None:
                        done = True
                        break
                    batch.append(json.dumps(item, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n')
                    if index == 127:
                        break
                    try:
                        item = self.queue.get_nowait()
                    except queue.Empty:
                        break
                if batch:
                    self.stream.writelines(batch)
                    self.stream.flush()
        except Exception as exc:
            self.error = exc
        finally:
            try:
                self.stream.close()
            except Exception as exc:
                self.error = self.error or exc

    def close(self):
        if not self.closed:
            self.closed = True
            while self.thread.is_alive() and self.error is None:
                try:
                    self.queue.put(None, timeout=.05)
                    break
                except queue.Full:
                    continue
            self.thread.join()
        if self.error:
            raise OSError('evidence writer failed: ' + str(self.error)) from self.error
