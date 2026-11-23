#include "monitor.h"
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
static uint64_t receive_tick;
static uint64_t clock_ticks(void){return receive_tick;}
static void publish(m_service *s,m_status *t,uint64_t entry,uint64_t sample,uint64_t received) {
    t->ping_seq=s->shared->control.ping_seq;t->ping_tick=sample;
    t->heartbeat=sample;t->temperature_tick=sample;receive_tick=received;
    m_status_publish(s->shared,t);m_service_poll(s,entry);
}
int main(void) {
    m_shared *p=calloc(1,sizeof(*p));assert(p);m_service s;
    m_service_init(&s,p,1000000,0,1000000);s.clock_ticks=clock_ticks;
    m_status t={.core=1,.hz=1000000,.epoch=1000000,.enabled=1,
        .configured=M_ALL_RAILS,.observed_mask=M_ALL_RAILS,.conversion_ready=M_ALL_RAILS,
        .profile_rails=E07_PROFILE_RAILS,.configured_tick=1000000,.temperature_valid=1};
    /* The boot request can legitimately expire while Core0 loads SD/network. */
    publish(&s,&t,2500000,2499990,2500010);
    assert(!s.clock_checks&&s.clock_rejections==1&&!s.faults);
    for(unsigned i=1;i<=3;i++) {
        uint64_t sent=s.ping_sent,entry=sent+10000;
        /* Core1 observed the request after poll entry, before coherent receipt. */
        publish(&s,&t,entry,entry+5,entry+10);
        assert(s.clock_checks==i);
        assert(s.last_clock_sent==sent&&s.last_clock_sampler==entry+5&&s.last_clock_received==entry+10);
        assert(s.last_clock_flags==M_VALID);
        if(i==3)assert(m_service_ready(&s,entry));
        /* Re-reading one pong must not increment the handshake count. */
        receive_tick=entry+20;m_service_poll(&s,entry+15);assert(s.clock_checks==i);
        receive_tick=sent+100010;m_service_poll(&s,sent+100000);
    }
    uint64_t sent=s.ping_sent;unsigned rejected=s.clock_rejections;
    publish(&s,&t,sent+10000,sent-1,sent+10010); /* before request */
    assert(!s.clock_checks&&s.clock_rejections==++rejected);
    receive_tick=sent+100010;m_service_poll(&s,sent+100000);sent=s.ping_sent;
    publish(&s,&t,sent+10000,sent+10050,sent+10010); /* genuinely after receipt */
    assert(!s.clock_checks&&s.clock_rejections==++rejected);
    receive_tick=sent+100010;m_service_poll(&s,sent+100000);sent=s.ping_sent;
    publish(&s,&t,sent+260000,sent+100,sent+260010); /* original250ms limit */
    assert(!s.clock_checks&&s.clock_rejections==++rejected);
    /* A backwards Core0 clock remains a genuine handshake fault during a phase. */
    sent=s.ping_sent;s.state=M_ACTIVE;
    publish(&s,&t,sent+10000,sent+100,sent+9999);
    assert(!s.clock_checks&&s.clock_rejections==++rejected&&(s.faults&M_FAULT_HANDSHAKE));
    free(p);puts("COHERENT_RECEIPT_CLOCK_THREE_PINGS_AND_REAL_FAULTS_OK");return 0;
}
