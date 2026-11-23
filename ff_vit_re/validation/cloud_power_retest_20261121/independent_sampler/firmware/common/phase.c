#include "monitor.h"
#include <string.h>
static void copy_to_shared(void *dst,const void *src,size_t n) {
    volatile unsigned char *d=dst;const unsigned char *s=src;
    while(n--)*d++=*s++;
}
static void copy_from_shared(void *dst,const void *src,size_t n) {
    unsigned char *d=dst;const volatile unsigned char *s=src;
    while(n--)*d++=*s++;
}
int m_publish_rail(m_shared *s,m_status *t,const m_rail_record *r) {
    if(t->rail_count>=M_RAIL_CAP){++t->overflows;t->faults|=M_FAULT_BUFFER;return -1;}
    m_rail_record record=*r;record.seq=t->rail_count;
    copy_to_shared(&s->rails[t->rail_count],&record,sizeof(record));
    __atomic_thread_fence(__ATOMIC_RELEASE);++t->rail_count;return 0;
}
int m_publish_temp(m_shared *s,m_status *t,const m_temperature *r) {
    if(t->temp_count>=M_TEMP_CAP){++t->overflows;t->faults|=M_FAULT_BUFFER;return -1;}
    m_temperature record=*r;record.seq=t->temp_count;
    copy_to_shared(&s->temperatures[t->temp_count],&record,sizeof(record));
    __atomic_thread_fence(__ATOMIC_RELEASE);++t->temp_count;return 0;
}
void m_status_publish(m_shared *s,const m_status *t) {
    uint32_t seq=__atomic_load_n(&s->status_seq,__ATOMIC_RELAXED);
    __atomic_store_n(&s->status_seq,seq|1u,__ATOMIC_SEQ_CST);
    /* STLR alone orders earlier stores, not the payload stores that follow.
       Publish the odd marker before any byte of the replacement is visible. */
    __atomic_thread_fence(__ATOMIC_RELEASE);
    copy_to_shared(&s->status,t,sizeof(*t));
    __atomic_store_n(&s->status_seq,(seq|1u)+1u,__ATOMIC_RELEASE);
}
int m_status_read(const m_shared *s,m_status *t) {
    for(unsigned retry=0;retry<8;retry++) {
        uint32_t a=__atomic_load_n(&s->status_seq,__ATOMIC_ACQUIRE);
        if(a&1u)continue;
        copy_from_shared(t,&s->status,sizeof(*t));
        __atomic_thread_fence(__ATOMIC_ACQUIRE);
        if(a==__atomic_load_n(&s->status_seq,__ATOMIC_ACQUIRE))return 0;
    }
    return -1;
}
void m_latest_publish(m_shared *s,const m_rail_record rows[M_RAILS]) {
    uint32_t seq=__atomic_load_n(&s->latest_seq,__ATOMIC_RELAXED);
    __atomic_store_n(&s->latest_seq,seq|1u,__ATOMIC_SEQ_CST);
    /* Same odd-before-payload ordering as status publication above. */
    __atomic_thread_fence(__ATOMIC_RELEASE);
    copy_to_shared(s->latest,rows,sizeof(s->latest));
    __atomic_store_n(&s->latest_seq,(seq|1u)+1u,__ATOMIC_RELEASE);
}
int m_latest_read(const m_shared *s,m_rail_record rows[M_RAILS]) {
    for(unsigned retry=0;retry<8;retry++) {
        uint32_t seq=__atomic_load_n(&s->latest_seq,__ATOMIC_ACQUIRE);
        if(seq&1u)continue;
        copy_from_shared(rows,s->latest,sizeof(s->latest));
        __atomic_thread_fence(__ATOMIC_ACQUIRE);
        if(seq==__atomic_load_n(&s->latest_seq,__ATOMIC_ACQUIRE))return 0;
    }
    return -1;
}
void m_service_init(m_service *s,m_shared *p,uint64_t hz,unsigned core,uint64_t epoch) {
    memset(s,0,sizeof(*s));s->shared=p;s->hz=hz;s->epoch=epoch;
    __atomic_store_n(&p->control.magic,0,__ATOMIC_RELEASE);
    m_control c={0};c.version=M_VERSION;c.core=core;c.hz=hz;c.epoch=epoch;
    c.profile_rails=E07_PROFILE_RAILS;memcpy(c.build_identity,M_BUILD_ID,sizeof(M_BUILD_ID));
    c.enabled=1;c.scan_ms=20;c.heartbeat=epoch;c.ping_tick=epoch;c.ping_seq=1;
    copy_to_shared(&p->control,&c,sizeof(c));s->ping_sent=epoch;
    __atomic_store_n(&p->control.magic,M_MAGIC,__ATOMIC_RELEASE);
}
int m_event_add(m_service *s,m_event e) {
    if(s->state==M_IDLE||s->state==M_DONE)return 0;
    if(s->event_count>=M_EVENT_CAP){s->faults|=M_FAULT_BUFFER;return -1;}
    e.seq=s->event_count;e.phase=s->phase;
    s->shared->events[s->event_count++]=e;return 0;
}
void m_fail(m_service *s,uint32_t fault,uint32_t id,uint64_t tick) {
    if(s->state==M_IDLE||s->state==M_DONE)return;
    if((s->faults&fault)!=fault) {
        m_event e={.type=M_EVENT_FAULT,.request_id=id,.flags=fault,.tick=tick};
        m_event_add(s,e);
    }
    s->faults|=fault;
}
static int ready_snapshot(const m_service *s,m_status t,uint64_t now) {
    return t.core==1&&t.epoch==s->epoch&&t.hz==s->hz&&t.configured==M_ALL_RAILS&&
        t.profile_rails==E07_PROFILE_RAILS&&t.observed_mask==M_ALL_RAILS&&
        (E07_PROFILE_RAILS!=18||(t.conversion_ready&M_REQUIRED_RAILS)==M_REQUIRED_RAILS)&&
        t.enabled&&s->shared->control.enabled&&!t.faults&&s->clock_checks>=3&&
        s->heartbeat_advances>=3&&now>=t.heartbeat&&now-t.heartbeat<=s->hz/4&&
        now>=t.configured_tick&&now-t.configured_tick>=s->hz&&t.temperature_valid&&
        now>=t.temperature_tick&&now-t.temperature_tick<=2*s->hz;
}
int m_service_ready(const m_service *s,uint64_t now) {
    m_status t;
    if(!s->shared||!s->hz||s->shared->control.core!=0||m_status_read(s->shared,&t))return 0;
    if(s->clock_ticks) {
        uint64_t received=s->clock_ticks();
        if(received<now)return 0;
        now=received;
    }
    return ready_snapshot(s,t,now);
}
static void clock_observation(m_service *s,const m_status *t,uint64_t received,int valid) {
    s->last_clock_sent=s->ping_sent;s->last_clock_sampler=t->ping_tick;
    s->last_clock_received=received;s->last_clock_flags=valid?M_VALID:M_CLOCK_ERROR;
    s->clock_checks=valid?s->clock_checks+1:0;
    if(!valid)++s->clock_rejections;
    m_event e={.type=M_EVENT_CLOCK,.flags=s->last_clock_flags,
        .begin=s->ping_sent,.end=received,.tick=t->ping_tick,.aux=t->ping_seq};
    m_event_add(s,e);
    if(!valid)m_fail(s,M_FAULT_HANDSHAKE,0,received);
}
void m_service_poll(m_service *s,uint64_t now) {
    m_status t;
    __atomic_store_n(&s->shared->control.heartbeat,now,__ATOMIC_RELEASE);
    if(m_status_read(s->shared,&t)) {
        if(now-s->last_heartbeat>s->hz/4)m_fail(s,M_FAULT_HANDSHAKE,0,now);
        return;
    }
    /* A sampler publication can occur between poll entry and status receipt.
       Comparing it with the entry tick incorrectly calls a real reply "future". */
    if(s->clock_ticks) {
        uint64_t received=s->clock_ticks();
        if(received<now) {clock_observation(s,&t,received,0);return;}
        now=received;
    }
    if(t.core==1&&t.hz==s->hz&&t.epoch==s->epoch) {
        if(t.heartbeat>s->last_heartbeat){++s->heartbeat_advances;s->last_heartbeat=t.heartbeat;}
        if(t.ping_seq==s->shared->control.ping_seq&&t.ping_seq!=s->last_pong) {
            int valid=t.ping_tick>=s->ping_sent&&t.ping_tick<=now&&now-s->ping_sent<=s->hz/4;
            s->last_pong=t.ping_seq;
            clock_observation(s,&t,now,valid);
        }
    } else {s->clock_checks=0;s->heartbeat_advances=0;}
    if(now-s->ping_sent>=s->hz/10 && s->last_pong==s->shared->control.ping_seq) {
        s->ping_sent=now;__atomic_store_n(&s->shared->control.ping_tick,now,__ATOMIC_RELEASE);
        __atomic_add_fetch(&s->shared->control.ping_seq,1,__ATOMIC_RELEASE);
    }
    if(s->state==M_IDLE||s->state==M_DONE)return;
    if(!ready_snapshot(s,t,now))m_fail(s,t.faults?t.faults:M_FAULT_HANDSHAKE,0,now);
    if(now>=s->t0&&!s->start_logged) {
        s->start_logged=1;m_event e={.type=M_EVENT_START,.tick=s->t0};m_event_add(s,e);
        if(t.phase!=s->phase)m_fail(s,M_FAULT_HANDSHAKE,0,now);
    }
    if(now>=s->t1&&!s->end_logged) {
        s->end_logged=1;m_event e={.type=M_EVENT_END,.tick=s->t1};m_event_add(s,e);
    }
    s->state=now<s->t0?M_GUARD:now<s->t1?M_ACTIVE:M_POST;
}
int m_arm(m_service *s,uint32_t seconds,uint64_t now) {
    m_status t;
    if(!seconds||seconds>150||s->state!=M_IDLE||s->pending_ack||!m_service_ready(s,now)||
       m_status_read(s->shared,&t)||t.state!=M_IDLE||t.rail_count||t.temp_count)return -1;
    s->faults=0;
    s->event_count=0;
    s->completed_full=0;
    s->completed_compact=0;
    s->completed_continuous=0;
    s->continuous_begin=0;
    s->continuous_end=0;
    s->start_logged=0;
    s->end_logged=0;
    ++s->phase;
    s->t0=now+s->hz+s->hz/4;
    s->t1=s->t0+seconds*s->hz;
    s->state=M_GUARD;
    m_control *c=&s->shared->control;
    c->phase=s->phase;
    c->t0=s->t0;
    c->t1=s->t1;
    c->command=M_CMD_ARM;
    /* The command sequence publishes all preceding control fields together. */
    __atomic_add_fetch(&c->command_seq,1,__ATOMIC_RELEASE);
    m_event e={.type=M_EVENT_ARM,.tick=now,.begin=s->t0,.end=s->t1,.mode=c->mode};
    return m_event_add(s,e);
}
int m_finish(m_service *s,uint64_t now) {
    m_status t;
    if(s->state==M_IDLE||s->state==M_DONE||s->pending_ack||now<s->t1+s->hz||
        m_status_read(s->shared,&t)||t.phase!=s->phase||t.state!=M_DONE)return -1;
    s->faults|=t.faults;
    m_event e={.type=M_EVENT_FINISH,.tick=now,.flags=s->faults};m_event_add(s,e);
    s->state=M_DONE;return 0;
}
int m_release(m_service *s) {
    if(s->state!=M_DONE||s->pending_ack)return -1;
    s->shared->control.command=M_CMD_RELEASE;
    __atomic_add_fetch(&s->shared->control.command_seq,1,__ATOMIC_RELEASE);
    s->state=M_IDLE;s->event_count=0;return 0;
}
int m_ack_begin(m_service *s,uint32_t id,uint32_t mode,uint32_t seq,uint64_t begin,uint64_t end) {
    if(s->pending_ack)return -1;
    s->pending_ack=1;s->pending_id=id;s->pending_mode=mode;s->pending_end_seq=seq;
    s->pending_begin=begin;s->pending_end=end;return 0;
}
void m_ack_poll(m_service *s,uint32_t ack,uint64_t now) {
    if(!s->pending_ack||(int32_t)(ack-s->pending_end_seq)<0)return;
    m_event e={.type=M_EVENT_ACK,.request_id=s->pending_id,.mode=s->pending_mode,
        .flags=M_VALID,.begin=s->pending_begin,.end=s->pending_end,.tick=now,.aux=ack};
    m_event_add(s,e);
    if(s->state!=M_IDLE&&s->state!=M_DONE&&now>=s->t0&&now<s->t1&&!s->faults) {
        if(s->pending_mode==M_LOAD_FULL)++s->completed_full;
        if(s->pending_mode==M_LOAD_COMPACT)++s->completed_compact;
    }
    s->pending_ack=0;
}
void m_inference_event(m_service *s,uint32_t id,uint64_t begin,uint64_t end,uint32_t mismatches,int ok) {
    uint32_t mode=s->shared->control.mode;
    m_event e={.type=ok?M_EVENT_INFERENCE:M_EVENT_INFERENCE_ERROR,.request_id=id,
        .mode=mode,.flags=ok?M_VALID:0,.mismatch_count=mismatches,.begin=begin,.end=end,.tick=end};
    m_event_add(s,e);
    if(!ok){m_fail(s,M_FAULT_INFERENCE,id,end);return;}
    if(mode==M_LOAD_CONTINUOUS&&s->state!=M_IDLE&&s->state!=M_DONE) {
        if(!s->continuous_begin)s->continuous_begin=begin;
        s->continuous_end=end;
        if(end>=s->t0&&end<s->t1&&!s->faults)++s->completed_continuous;
    }
}
