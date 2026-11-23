/* Catches overwrite/publication, pre-ACK counting, request loss, boundary/fault acceptance. */
#include "monitor.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static void reply(m_service *s,m_status *st,uint64_t now){
    st->heartbeat=now;st->ping_seq=s->shared->control.ping_seq;
    st->ping_tick=s->shared->control.ping_tick+1;
    m_status_publish(s->shared,st);m_service_poll(s,now+2);
}
static void latest_publication_is_a_complete_snapshot(m_shared *p) {
    m_rail_record rows[M_RAILS],observed[M_RAILS];
    for(unsigned rail=0;rail<M_RAILS;rail++) {
        memset(&rows[rail],(int)(rail+1),sizeof(rows[rail]));
        rows[rail].rail=(uint16_t)rail;
    }
    p->latest_seq=UINT32_MAX-1u;
    m_latest_publish(p,rows);
    assert(p->latest_seq==0); /* generation wrap remains even and readable */
    assert(!m_latest_read(p,observed));
    assert(!memcmp(rows,observed,sizeof(rows)));
    p->latest_seq=1;
    p->latest[17].power_uW=123; /* an in-progress partial replacement is rejected */
    assert(m_latest_read(p,observed)!=0);
    m_latest_publish(p,rows);
    assert(!m_latest_read(p,observed));
    assert(!memcmp(rows,observed,sizeof(rows)));
}
int main(void){
    m_shared *p=calloc(1,sizeof(*p));assert(p);m_status st={0},got={0};
    latest_publication_is_a_complete_snapshot(p);
    m_rail_record row={.phase=7,.power_uW=6000000};
    assert(m_publish_rail(p,&st,&row)==0&&st.rail_count==1);
    m_status_publish(p,&st);assert(m_status_read(p,&got)==0&&got.rail_count==1);
    assert(p->rails[0].seq==0&&p->rails[0].phase==7&&p->rails[0].power_uW==6000000);
    st.rail_count=M_RAIL_CAP;assert(m_publish_rail(p,&st,&row)!=0);
    assert(st.overflows==1&&(st.faults&M_FAULT_BUFFER)&&p->rails[0].phase==7);
    m_temperature temp={.temperature_mC=42000};st.temp_count=M_TEMP_CAP;
    assert(m_publish_temp(p,&st,&temp)!=0&&st.overflows==2);
    p->status_seq=1;assert(m_status_read(p,&got)!=0);p->status_seq=2;
    m_service s={0};m_service_init(&s,p,1000,0,99);
    assert(m_arm(&s,120,100)!=0); /* no sampler cannot arm */
    memset(&st,0,sizeof(st));st.core=1;st.hz=1000;st.epoch=99;
    st.profile_rails=18;st.observed_mask=262143;st.configured=M_ALL_RAILS;st.conversion_ready=M_ALL_RAILS;st.configured_tick=1;st.enabled=1;
    st.temperature_valid=1;st.temperature_tick=1100;
    reply(&s,&st,1100);reply(&s,&st,1200);reply(&s,&st,1300);reply(&s,&st,1400);
    assert(m_service_ready(&s,1403));
    st.faults=M_FAULT_CONFIG;m_status_publish(p,&st);assert(m_arm(&s,120,1403)!=0);
    st.faults=0;m_status_publish(p,&st);assert(m_arm(&s,151,1403)!=0);
    assert(m_arm(&s,2,1403)==0&&s.t0==2653&&s.t1==4653&&s.phase==1);
    assert(m_arm(&s,1,1404)!=0);st.phase=1;st.state=M_GUARD;
    assert(m_ack_begin(&s,41,M_LOAD_FULL,100,2000,2200)==0);
    m_ack_poll(&s,99,2653);assert(s.completed_full==0&&s.pending_ack);
    m_ack_poll(&s,100,2653);assert(s.completed_full==1&&!s.pending_ack);
    assert(p->events[s.event_count-1].request_id==41&&p->events[s.event_count-1].tick==2653);
    assert(m_ack_begin(&s,42,M_LOAD_COMPACT,3,4300,4350)==0);
    m_ack_poll(&s,0xfffffff0u,4400);assert(s.completed_compact==0);
    m_ack_poll(&s,3,4653);assert(s.completed_compact==0); /* [t0,t1) */
    assert(m_ack_begin(&s,43,M_LOAD_COMPACT,20,2400,2500)==0);
    m_ack_poll(&s,20,2700);assert(s.completed_compact==1);
    s.shared->control.mode=M_LOAD_CONTINUOUS;
    m_inference_event(&s,0,2700,2800,0,1);assert(s.completed_continuous==1);
    m_inference_event(&s,0,4300,4653,0,1);assert(s.completed_continuous==1);
    st.faults=M_FAULT_SENSOR;reply(&s,&st,2800);assert(s.faults&M_FAULT_SENSOR);
    assert(m_finish(&s,5652)!=0);st.state=M_DONE;m_status_publish(p,&st);
    assert(m_finish(&s,5653)==0&&s.state==M_DONE);
    assert(m_release(&s)==0&&s.state==M_IDLE&&s.event_count==0);
    m_service_init(&s,p,1000,0,100);st.epoch=100;st.faults=0;st.phase=0;st.state=0;st.rail_count=0;
    reply(&s,&st,2000);reply(&s,&st,2100);reply(&s,&st,2200);reply(&s,&st,2300);
    assert(!m_service_ready(&s,2600)); /* stalled heartbeat */
    st.core=0;reply(&s,&st,2400);assert(!m_service_ready(&s,2402));
    st.core=1;st.ping_tick=999999;m_status_publish(p,&st);m_service_poll(&s,2500);
    assert(!m_service_ready(&s,2500));
    s.state=M_ACTIVE;s.last_heartbeat=2300;p->status_seq=1;
    m_service_poll(&s,3000);assert(s.faults&M_FAULT_HANDSHAKE);
    free(p);puts("PUBLICATION_PHASE_ACK_FAULT_OK");return 0;
}
