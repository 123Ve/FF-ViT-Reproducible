#include "sampler.h"
#include <string.h>
int m_sampler_init(m_sampler *s,m_shared *p,m_io io,unsigned core,uint64_t hz,int (*temp)(uint32_t *,int32_t *)) {
    memset(s,0,sizeof(*s));s->shared=p;s->io=io;s->temperature=temp;
    s->status.core=core;s->status.hz=hz;s->status.epoch=p->control.epoch;
    s->status.profile_rails=E07_PROFILE_RAILS;
    if(p->control.profile_rails!=E07_PROFILE_RAILS||
       memcmp(p->control.build_identity,M_BUILD_ID,sizeof(M_BUILD_ID))||core!=1||p->control.core!=0||p->control.hz!=hz||p->control.version!=M_VERSION)
        s->status.faults|=M_FAULT_HANDSHAKE;
    for(unsigned rail=0;rail<M_RAILS;rail++) {
        m_config_record record;
        if(!m_configure(&s->io,rail,&record))s->status.configured|=1u<<rail;
        else s->status.faults|=M_FAULT_CONFIG;
        p->configuration[rail]=record;
    }
    s->status.configured_tick=io.ticks(io.ctx);
    /* Zero means no actual post-configuration CVRF has been observed. */
    s->status.heartbeat=s->status.configured_tick;s->status.enabled=p->control.enabled;
    s->published_tick=s->status.configured_tick;
    m_status_publish(p,&s->status);return s->status.faults?-1:0;
}
void m_sampler_step(m_sampler *s) {
    m_control *c=&s->shared->control;m_status *st=&s->status;
    uint64_t now=s->io.ticks(s->io.ctx);
    uint32_t seq=__atomic_load_n(&c->command_seq,__ATOMIC_ACQUIRE);
    if(seq!=s->command_seq) {
        s->command_seq=seq;
        if(c->command==M_CMD_ARM&&st->state==M_IDLE) {
            st->phase=c->phase;s->t0=c->t0;s->t1=c->t1;st->state=M_GUARD;
            s->next_scan=now+c->offset_ms*st->hz/1000;
            if(s->next_scan>s->t0||s->t0-s->next_scan<st->hz)
                st->faults|=M_FAULT_HANDSHAKE;
        } else if(c->command==M_CMD_RELEASE&&st->state==M_DONE) {
            st->phase=0;st->state=M_IDLE;st->rail_count=st->temp_count=st->scan_count=0;
        } else st->faults|=M_FAULT_HANDSHAKE;
    }
    st->enabled=__atomic_load_n(&c->enabled,__ATOMIC_ACQUIRE);
    if(st->state!=M_IDLE&&st->state!=M_DONE) {
        st->state=now<s->t0?M_GUARD:now<s->t1?M_ACTIVE:now<s->t1+st->hz?M_POST:M_DONE;
        if(!st->enabled)st->faults|=M_FAULT_SENSOR;
    }
    int logging=st->state==M_GUARD||st->state==M_ACTIVE||st->state==M_POST;
    if(now>=s->next_temperature) {
        m_temperature t={.phase=st->phase,.tick=now,.temperature_mC=INT32_MIN};
        if(!s->temperature(&t.raw,&t.temperature_mC))t.flags=M_VALID;
        else{++st->temp_errors;st->faults|=M_FAULT_TEMP;}
        st->temperature_mC=t.temperature_mC;st->temperature_valid=(t.flags&M_VALID)!=0;
        st->temperature_tick=now;s->next_temperature=now+st->hz;
        if(logging)m_publish_temp(s->shared,st,&t);
    }
    if(st->enabled&&now>=s->next_scan) {
        uint32_t period=c->scan_ms;
        if(period!=17&&period!=20&&period!=23){st->faults|=M_FAULT_CONFIG;period=20;}
        uint64_t step=period*st->hz/1000;
        st->scan_start=now;
        int first_phase_scan=logging&&st->rail_count==0;
        m_rail_record latest[M_RAILS];int invalid=0;
        for(unsigned rail=0;rail<M_RAILS;rail++) {
            m_rail_record r;
            int unqualified=!(st->observed_mask&(1u<<rail));
            int result=m_sample(&s->io,rail,st->hz,&s->fresh[rail],&r);
            uint64_t configured=s->shared->configuration[rail].end;
            if(unqualified) {
                uint64_t observation=(r.flags&M_FRESH)?r.end[4]:r.end[3];
                if(observation<configured||observation-configured>st->hz*150u/1000u) {
                    r.flags=(r.flags&~M_VALID)|M_STALE;r.power_uW=INT64_MIN;result=-1;
                } else if(!result&&!(r.flags&M_FRESH)) {
                    /* A rejected first observation cannot license held data. */
                    r.flags=(r.flags&~M_VALID)|M_NOT_READY;r.power_uW=INT64_MIN;result=1;
                }
            }
            if(result>0) {
                if(logging||r.end[3]<configured||r.end[3]-configured>st->hz*150u/1000u) {
                    r.flags|=M_STALE;result=-1;
                } else ++st->initializing_samples;
            }
            /* ADC observation is independent of signed measurement quality. */
            if((r.flags&M_FRESH)&&!(r.flags&(M_I2C_ERROR|M_CLOCK_ERROR|M_STALE)))
                st->observed_mask|=1u<<rail;
            int diagnostic_negative=E07_PROFILE_RAILS!=18&&
                (r.flags==M_NEGATIVE||r.flags==(M_NEGATIVE|M_FRESH))&&
                (!unqualified||(r.flags&M_FRESH));
            if(result<0&&diagnostic_negative) {
                if(M_REQUIRED_RAILS&(1u<<rail))++st->included_negative_samples;
                else ++st->excluded_negative_samples;
            } else if(result<0) {
                invalid=1;
                ++st->invalid_samples;st->faults|=M_FAULT_SENSOR;
                if(r.flags&M_I2C_ERROR)++st->i2c_errors;
                if(r.flags&M_STALE)++st->stale_samples;
            } else if(!result&&(r.flags&M_FRESH)) {
                st->conversion_ready|=1u<<rail;
            }
            if(first_phase_scan&&(s->t0<st->hz||r.end[3]>s->t0-st->hz))
                st->faults|=M_FAULT_HANDSHAKE;
            r.phase=st->phase;r.scan=st->scan_count;r.scan_start=now;
            r.seq=rail;latest[rail]=r;
            if(logging)m_publish_rail(s->shared,st,&r);
        }
        if(!s->diagnostic_frozen)m_latest_publish(s->shared,latest);
        if(invalid)s->diagnostic_frozen=1; /* Preserve first bad raw scan, including before arm. */
        ++st->scan_count;s->next_scan=now+step;
        if(s->io.ticks(s->io.ctx)>s->next_scan)++st->scan_overruns;
    }
    uint32_t ping=__atomic_load_n(&c->ping_seq,__ATOMIC_ACQUIRE);
    uint64_t heartbeat=s->io.ticks(s->io.ctx);
    if(ping!=st->ping_seq) {
        st->ping_seq=ping;
        st->ping_tick=heartbeat; /* First actual observation, fixed for this request. */
    }
    st->heartbeat=heartbeat; /* Liveness continues without rewriting the pong. */
    if(st->heartbeat-s->published_tick>=st->hz/1000) {
        m_status_publish(s->shared,st);s->published_tick=st->heartbeat;
    }
}
