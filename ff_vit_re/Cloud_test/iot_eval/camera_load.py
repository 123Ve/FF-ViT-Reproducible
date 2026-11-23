"""Independent virtual capture with bounded FIFOs and one serial consumer.

Only frame descriptors are queued. Payloads and socket ownership belong to the
consumer. All timing is on the host monotonic clock, never a board clock estimate.
"""
from collections import deque
from dataclasses import asdict, dataclass
import math
import threading
import time

from Cloud_test.iot_eval.cloud_measurements import percentile


@dataclass(slots=True)
class Frame:
    stream_id: int
    sequence: int
    scheduled_ns: int
    capture_ns: int
    status: str = 'queued'
    dispatch_ns: int | None = None
    deadline_ns: int | None = None
    send_monotonic_ns: int | None = None
    receive_monotonic_ns: int | None = None
    terminal_ns: int | None = None
    socket_sent_bytes: int = 0
    socket_received_bytes: int = 0
    request_id: int | None = None
    failure: str | None = None


class CameraQueues:
    def __init__(self, streams, capacity, emit=None):
        if type(streams) is not int or streams < 1 or type(capacity) is not int or capacity < 1:
            raise ValueError('streams and queue capacity must be positive integers')
        self.queues = [deque() for _ in range(streams)]
        self.capacity = capacity
        self.condition = threading.Condition()
        self.records = []
        self.high_water = [0] * streams
        self.finished = 0
        self.cursor = 0
        self.emit = emit or (lambda event: None)

    def put(self, frame):
        if not 1 <= frame.stream_id <= len(self.queues):
            raise ValueError('invalid stream ID')
        dropped = None
        with self.condition:
            queue = self.queues[frame.stream_id - 1]
            if len(queue) == self.capacity:
                dropped = queue.popleft()
                dropped.status = 'dropped_oldest'
                dropped.terminal_ns = frame.capture_ns
            queue.append(frame)
            self.records.append(frame)
            self.high_water[frame.stream_id - 1] = max(self.high_water[frame.stream_id - 1], len(queue))
            capture_event = {'kind': 'capture', **asdict(frame)}
            drop_event = {'kind': 'drop', **asdict(dropped)} if dropped is not None else None
            self.condition.notify()
        self.emit(capture_event)
        if drop_event is not None:
            self.emit(drop_event)

    def get_next(self):
        with self.condition:
            for offset in range(len(self.queues)):
                index = (self.cursor + offset) % len(self.queues)
                if self.queues[index]:
                    self.cursor = (index + 1) % len(self.queues)
                    return self.queues[index].popleft()
        return None

    def wait(self, seconds):
        with self.condition:
            if not any(self.queues) and self.finished != len(self.queues):
                self.condition.wait(seconds)

    def producer_finished(self):
        with self.condition:
            self.finished += 1
            self.condition.notify_all()


def _latencies(rows, name, left, right):
    values = [(row[right] - row[left]) / 1e6 for row in rows]
    return {name + '_mean': sum(values) / len(values) if values else None,
            **{name + '_' + label: percentile(values, quantile)
               for label, quantile in [('p50', .5), ('p95', .95), ('p99', .99)]}}


def summarize_condition(records, start_ns, end_ns, streams, missed_slots):
    """Summarize completed transactions, attributing whole bytes at completion.

    Throughput, latency samples and byte rates exclude responses received during
    drain. Counts include all produced frames, making loss and drain auditable.
    """
    elapsed = (end_ns - start_ns) / 1e9
    if elapsed <= 0:
        raise ValueError('measurement window must be positive')

    def summarize(rows, missed):
        completed = [r for r in rows if r['status'] == 'completed']
        active = [r for r in completed if start_ns <= r['receive_monotonic_ns'] < end_ns]
        drops = sum(r['status'] == 'dropped_oldest' for r in rows)
        failed = sum(r['status'] == 'failed' for r in rows)
        pending = sum(r['status'] == 'pending_at_stop' for r in rows)
        backlog = sum(r['capture_ns'] < end_ns and r['status'] != 'dropped_oldest'
                      and (r.get('terminal_ns') or r.get('receive_monotonic_ns') or end_ns) >= end_ns
                      for r in rows)
        up = sum(r.get('socket_sent_bytes', 0) for r in active)
        down = sum(r.get('socket_received_bytes', 0) for r in active)
        result = dict(elapsed_s=elapsed, produced=len(rows), capture_fps=len(rows) / elapsed,
            source_missed_slots=missed, completed_active=len(active), completed_total=len(completed),
            completed_drain=len(completed) - len(active), dropped_oldest=drops, failed=failed,
            pending_at_stop=pending, end_window_backlog=backlog, fps=len(active) / elapsed,
            drop_rate=drops / len(rows) if rows else 0.0,
            unserved_fraction=(drops + failed + pending) / len(rows) if rows else 0.0,
            request_application_bytes=up, response_application_bytes=down,
            request_application_mbit_s=up * 8 / elapsed / 1e6,
            response_application_mbit_s=down * 8 / elapsed / 1e6,
            bidirectional_application_mbit_s=(up + down) * 8 / elapsed / 1e6,
            conservation_ok=len(rows) == len(completed) + drops + failed + pending)
        for name, left, right in [('queue_ms', 'capture_ns', 'dispatch_ns'),
                ('service_ms', 'send_monotonic_ns', 'receive_monotonic_ns'),
                ('e2e_ms', 'capture_ns', 'receive_monotonic_ns'),
                ('producer_lateness_ms', 'scheduled_ns', 'capture_ns')]:
            result.update(_latencies(active, name, left, right))
        return result

    per_stream = [dict(stream_id=i, **summarize([r for r in records if r['stream_id'] == i], missed_slots[i-1]))
                  for i in range(1, streams + 1)]
    return dict(summary=summarize(records, sum(missed_slots)), per_stream=per_stream)


def run_condition(service, streams, fps, duration, capacity=3, drain_timeout=5, emit=None):
    if (type(streams) is not int or streams < 1 or type(capacity) is not int or capacity < 1
            or any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0
                   for v in (fps, duration, drain_timeout))):
        raise ValueError('streams/capacity must be positive integers; rates and times finite and positive')
    emit = emit or (lambda event: None)
    queues = CameraQueues(streams, capacity, emit)
    stop = threading.Event()
    ready = threading.Barrier(streams + 1)
    missed = [0] * streams
    errors = []
    start_ns = time.monotonic_ns()
    end_ns = start_ns + round(duration * 1e9)
    slots = math.ceil(duration * fps - 1e-9)

    def producer(stream_id):
        try:
            ready.wait()
            index = 0
            while index < slots and not stop.is_set():
                scheduled = start_ns + round(index * 1e9 / fps)
                if stop.wait(max(0, (scheduled - time.monotonic_ns()) / 1e9)):
                    break
                now = time.monotonic_ns()
                if now >= end_ns:
                    missed[stream_id - 1] += slots - index
                    break
                # Do not synthesize a burst of captures after a host scheduling stall.
                expired = min(slots - index - 1, max(0, int((now - scheduled) * fps / 1e9)))
                if expired:
                    missed[stream_id - 1] += expired
                    index += expired
                    scheduled = start_ns + round(index * 1e9 / fps)
                queues.put(Frame(stream_id, index + 1, scheduled, now))
                index += 1
        except Exception as exc:
            errors.append(exc)
            stop.set()
        finally:
            queues.producer_finished()

    threads = [threading.Thread(target=producer, args=(i,), name=f'e07-camera-{i}')
               for i in range(1, streams + 1)]
    started = []
    failure = None
    interrupted = False
    try:
        for thread in threads:
            thread.start()
            started.append(thread)
        start_ns = time.monotonic_ns() + 10_000_000
        end_ns = start_ns + round(duration * 1e9)
        drain_end_ns = end_ns + round(drain_timeout * 1e9)
        ready.wait()
        while time.monotonic_ns() < drain_end_ns:
            if errors:
                raise errors[0]
            frame = queues.get_next()
            if frame is None:
                if queues.finished == streams:
                    break
                queues.wait(.01)
                continue
            frame.dispatch_ns = time.monotonic_ns()
            frame.deadline_ns = drain_end_ns
            frame.status = 'in_flight'
            try:
                emit({'kind': 'dispatch', **asdict(frame)})
                event = service(frame)
                for name in ('send_monotonic_ns', 'receive_monotonic_ns', 'socket_sent_bytes',
                             'socket_received_bytes', 'request_id'):
                    if name in event:
                        setattr(frame, name, event[name])
                if (frame.send_monotonic_ns is None or frame.receive_monotonic_ns is None
                        or not frame.capture_ns <= frame.dispatch_ns <= frame.send_monotonic_ns <= frame.receive_monotonic_ns):
                    raise ValueError('invalid host transaction timestamps')
                frame.status = 'completed'
                frame.terminal_ns = frame.receive_monotonic_ns
                emit({'kind': 'completed', **event, **asdict(frame)})
            except BaseException as exc:
                frame.status = 'failed'
                frame.failure = str(exc) or type(exc).__name__
                frame.terminal_ns = time.monotonic_ns()
                diagnostic = getattr(exc, 'diagnostic', {})
                for name in ('send_monotonic_ns', 'socket_sent_bytes', 'socket_received_bytes', 'request_id'):
                    if name in diagnostic:
                        setattr(frame, name, diagnostic[name])
                emit({**diagnostic, 'kind': 'transaction_failure', 'stream_id': frame.stream_id,
                      'sequence': frame.sequence, 'failure': frame.failure,
                      'failed_monotonic_ns': frame.terminal_ns})
                raise
    except BaseException as exc:
        failure = str(exc) or type(exc).__name__
        interrupted = isinstance(exc, KeyboardInterrupt)
        end_ns = min(end_ns, max(start_ns + 1, time.monotonic_ns()))
    finally:
        # Normal completion also waits out the production window; a fast consumer
        # must not stop at the final scheduled capture before the deadline.
        if failure is None:
            try:
                stop.wait(max(0, (end_ns - time.monotonic_ns()) / 1e9))
            except KeyboardInterrupt:
                failure = 'KeyboardInterrupt'
                interrupted = True
                end_ns = min(end_ns, max(start_ns + 1, time.monotonic_ns()))
        stop.set()
        ready.abort()
        for thread in started:
            thread.join()
        if errors and failure is None:
            failure = str(errors[0])
        finished_ns = time.monotonic_ns()
        for frame in queues.records:
            if frame.status == 'queued':
                frame.status = 'pending_at_stop'
                frame.terminal_ns = finished_ns
    records = [asdict(frame) for frame in queues.records]
    result = summarize_condition(records, start_ns, end_ns, streams, missed)
    result.update(status='ABORTED' if interrupted else 'FAIL' if failure else 'COMPLETE',
        failure=failure, start_monotonic_ns=start_ns, end_monotonic_ns=end_ns,
        finished_monotonic_ns=finished_ns, requested_duration_s=duration,
        drain_elapsed_s=max(0, (finished_ns - end_ns) / 1e9),
        queue_high_water=queues.high_water, records=records)
    return result
