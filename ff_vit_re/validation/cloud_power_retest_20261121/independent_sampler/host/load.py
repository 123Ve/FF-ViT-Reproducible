"""Independent absolute schedules; producer threads never access the socket."""
from bisect import bisect_left
import collections
import math
import threading
import time


def missed_in_window(event,fps,window):
    """Count scheduled deadlines in the half-open host window, even across a long stall."""
    if window is None:return 0
    slots=range(event['first_sequence'],event['first_sequence']+event['count'])
    def deadline(slot):return event['schedule_start_monotonic']+slot/fps
    return bisect_left(slots,window[1],key=deadline)-bisect_left(slots,window[0],key=deadline)


class OfferedLoad:
    def __init__(self, fps, record=None, clock=time.monotonic, phase=None, input_sha256=None):
        if fps<=0:raise ValueError('fps must be positive')
        self.fps=fps
        self.record=record or (lambda e:None)
        self.clock=clock
        self.phase=phase
        self.input_sha256=input_sha256
        self.queues=[collections.deque() for _ in range(4)]
        self.next_slots=[0]*4
        self.frames=[]
        self.missed=[]
        self.lock=threading.RLock()
        self.halt=threading.Event()
        self.threads=[]
        self.start_at=0
        self.window=None
        self.cursor=0

    def produce_due(self, stream, now):
        with self.lock:
            due=math.floor((now-self.start_at)*self.fps+1e-9)
            previous=self.next_slots[stream]
            if due<previous:return
            if due>previous:
                event=dict(event='missed_slots',stream=stream,first_sequence=previous,
                           count=due-previous,phase=self.phase,host_monotonic=now,schedule_start_monotonic=self.start_at)
                self.missed.append(event);self.record(event)
            f=dict(event='produced',stream=stream,sequence=due,phase=self.phase,
                   input_sha256=self.input_sha256,planned_monotonic=self.start_at+due/self.fps,
                   produced_monotonic=now,state='queued')
            self.frames.append(f);self.record(dict(f))
            q=self.queues[stream]
            if len(q)==3:
                old=q.popleft();old['state']='evicted'
                self.record(dict(event='evicted',stream=stream,sequence=old['sequence'],
                                 phase=self.phase,host_monotonic=now))
            q.append(f);self.next_slots[stream]=due+1

    def _producer(self,stream):
        while not self.halt.is_set():
            deadline=self.start_at+self.next_slots[stream]/self.fps
            delay=deadline-self.clock()
            if delay>0:
                self.halt.wait(delay)
            else:self.produce_due(stream,self.clock())

    def start(self):
        self.start_at=self.clock()
        self.threads=[threading.Thread(target=self._producer,args=(s,),name=f'producer-{s}') for s in range(4)]
        for t in self.threads:t.start()

    def stop(self):
        self.halt.set()
        for t in self.threads:t.join()

    def pop(self):
        with self.lock:
            for n in range(4):
                s=(self.cursor+n)%4
                if self.queues[s]:
                    self.cursor=(s+1)%4
                    return self.queues[s].popleft()
        return None

    def submit(self,frame,request_id):
        with self.lock:
            frame.update(state='submitted',request_id=request_id,submitted_monotonic=self.clock())
            self.record(dict(frame,event='submitted'))

    def complete(self,frame,now,success,error=None,failure_type=None,response_metadata=None):
        with self.lock:
            frame.update(state='completed' if success else 'failed',received_monotonic=now,
                         verified=bool(success),error=error,
                         e2e_seconds=now-frame['produced_monotonic'],
                         transaction_seconds=now-frame['submitted_monotonic'])
            frame['failure_type']=failure_type
            if response_metadata is not None:frame['board_response']=response_metadata
            self.record(dict(frame,event=frame['state']))

    def counts(self):
        with self.lock:
            values=collections.Counter(f['state'] for f in self.frames)
            submitted=sum('submitted_monotonic' in f for f in self.frames)
            window=self.window
            completed=[f for f in self.frames if f['state']=='completed']
            within=[f for f in completed if window and window[0]<=f['received_monotonic']<window[1]]
            drain=[f for f in completed if window and f['received_monotonic']>=window[1]]
            def in_window(t):return window is not None and window[0]<=t<window[1]
            produced_window=[f for f in self.frames if in_window(f['produced_monotonic'])]
            submitted_window=[f for f in self.frames if in_window(f.get('submitted_monotonic',float('-inf'))) ]
            return dict(missed_slots=sum(e['count'] for e in self.missed),produced=len(self.frames),
                scheduled_slots=sum(self.next_slots),
                window_missed_slots=sum(missed_in_window(e,self.fps,window) for e in self.missed),
                window_produced=len(produced_window),window_submitted=len(submitted_window),
                window_evicted=sum(f['state']=='evicted' for f in produced_window),
                window_failed=sum(f['state']=='failed' for f in produced_window),
                host_fps=len(within)/(window[1]-window[0]) if window else None,
                submitted=submitted,completed=len(completed),completed_window=len(within),
                completed_drain=len(drain),completed_pre_window=len(completed)-len(within)-len(drain),
                evicted=values['evicted'],failed=values['failed'],remaining=values['queued'],
                timeouts=sum(f.get('failure_type') in ('TimeoutError','timeout') for f in self.frames),
                in_flight=values['submitted'],conserved=(len(self.frames)==sum(values.values()) and
                    sum(self.next_slots)==len(self.frames)+sum(e['count'] for e in self.missed) and
                    submitted==values['submitted']+values['completed']+values['failed'] and
                    len(self.frames)==values['evicted']+values['queued']+submitted))
