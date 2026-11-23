#include "e06_network.h"
#include "e06_inference.h"
#include "fvit_protocol.h"
#include "fake_lwip.h"
#include "monitor.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
m_service m_runtime;
void fake_lwip_reset(void);struct tcp_pcb *fake_last_pcb(void);
err_t fake_connect_success(void);void fake_ack_all(void);
const unsigned char *fake_wire(void);size_t fake_wire_size(void);void fake_wire_clear(void);
void fake_inference_failure(int);
void fake_fail_write(int);void fake_fail_output(int);void fake_remote_error(err_t);
int fake_telemetry_calls(void);
static fvit_header_t response(void){fvit_header_t h;assert(!fvit_header_decode(&h,fake_wire()));return h;}
static err_t send_frame_result(const char *json,uint32_t id,int payload,int corrupt){
    size_t size=payload?e06_inference_input_bytes():0,n=strlen(json);
    unsigned char *frame=malloc(20+n+size);assert(frame);
    fvit_header_t h={7,id,(uint32_t)n,(uint32_t)size};assert(!fvit_header_encode(frame,&h));
    memcpy(frame+20,json,n);if(size)memcpy(frame+20+n,e06_inference_input_data(),size);
    if(corrupt)frame[20+n+size-1]^=1;
    struct tcp_pcb *pcb=fake_last_pcb();
    err_t status=ERR_OK;
    for(size_t offset=0;offset<20+n+size&&status==ERR_OK;){
        size_t count=20+n+size-offset;if(count>1000)count=1000;
        struct pbuf p={NULL,frame+offset,(u16_t)count,(u16_t)count};
        status=pcb->recv_cb(pcb->callback_arg,pcb,&p,ERR_OK);offset+=count;
    }free(frame);return status;
}
static void send_frame(const char *json,uint32_t id,int payload,int corrupt){
    assert(send_frame_result(json,id,payload,corrupt)==ERR_OK);
}
static void command(const char *name,const char *args){char j[256];snprintf(j,sizeof(j),"{\"name\":\"%s\",\"arguments\":%s}",name,args);send_frame(j,77,0,0);}
static void next(void){fake_ack_all();fake_wire_clear();}
static void fresh_connection(m_shared *shared,unsigned state,unsigned mode){
    m_service_init(&m_runtime,shared,1000000,0,1);
    fake_lwip_reset();fake_inference_failure(0);
    assert(!e06_network_start());assert(!fake_connect_success());next();
    m_runtime.phase=9;m_runtime.state=state;m_runtime.t0=1000;m_runtime.t1=1000000;
    shared->control.mode=mode;m_test_ticks=2000;
}
static unsigned fatal_failure_cases(m_shared *shared){
    /* Removing in-phase faulting before pending_ack must fail every open-state case. */
    const char *names[]={"invalid_header","unsupported_frame","Full_prefix_write",
        "Compact_write","Compact_output","remote_close","remote_error","receive_error"};
    unsigned failures=0;
    for(unsigned state=M_GUARD;state<=M_POST;state++)for(unsigned which=0;which<8;which++){
        fresh_connection(shared,state,which==2?M_LOAD_FULL:M_LOAD_COMPACT);
        struct tcp_pcb *pcb=fake_last_pcb();uint32_t expected_id=0;
        assert(!m_runtime.pending_ack);
        if(which<2){
            uint8_t bytes[20];fvit_header_t header={which?4:7,701,0,0};
            assert(!fvit_header_encode(bytes,&header));
            if(!which)bytes[0]=0;else expected_id=701;
            struct pbuf packet={NULL,bytes,20,20};
            assert(pcb->recv_cb(pcb->callback_arg,pcb,&packet,ERR_OK)==ERR_ABRT);
        }else if(which<5){
            expected_id=702+which;
            if(which==4)fake_fail_output(1);else fake_fail_write(1);
            const char *json=which==2?"{\"name\":\"replay_full\",\"arguments\":{}}":
                "{\"name\":\"replay_compact\",\"arguments\":{}}";
            assert(send_frame_result(json,expected_id,1,0)==ERR_ABRT);
        }else if(which==5){
            assert(pcb->recv_cb(pcb->callback_arg,pcb,NULL,ERR_OK)==ERR_OK);
        }else if(which==6){
            fake_remote_error(ERR_ABRT);
        }else{
            assert(pcb->recv_cb(pcb->callback_arg,pcb,NULL,ERR_ARG)==ERR_ABRT);
        }
        int fault_event=0;
        for(unsigned i=0;i<m_runtime.event_count;i++){
            const m_event *event=&shared->events[i];
            if(event->type==M_EVENT_FAULT&&event->flags==M_FAULT_NETWORK&&
               event->request_id==expected_id&&event->phase==9)fault_event=1;
        }
        if(!(m_runtime.faults&M_FAULT_NETWORK)||!fault_event){
            fprintf(stderr,"MISSING_FATAL_NETWORK_FAULT state=%u case=%s request=%u\n",state,names[which],expected_id);
            ++failures;
        }
        assert(!m_runtime.pending_ack&&!m_runtime.completed_full&&!m_runtime.completed_compact);
    }
    for(unsigned state=M_IDLE;state<=M_DONE;state+=M_DONE){
        fresh_connection(shared,state,M_LOAD_IDLE);
        fake_remote_error(ERR_ABRT);
        assert(!m_runtime.faults&&!m_runtime.event_count);
    }
    return failures;
}
int main(void){
    m_shared *shared=calloc(1,sizeof(*shared));assert(shared);
    m_service_init(&m_runtime,shared,1000000,0,1);
    fake_lwip_reset();assert(!e06_network_start());assert(!fake_connect_success());
    assert(response().kind==5);next();command("power_status","{}");
    assert(response().kind==6&&response().request_id==77);
    shared->latest[15].rail=15;shared->latest[15].shunt=65534;shared->latest[15].flags=256;
    next();command("power_export_latest","{\"count\":0}");
    assert(response().kind==1&&response().payload_len==18*128);
    const m_rail_record *latest=(const m_rail_record *)(fake_wire()+20+response().metadata_len);
    assert(latest[15].shunt==65534&&latest[15].flags==256);
    shared->latest_seq=1;next();command("power_export_latest","{\"count\":0}");
    assert(response().kind==255);shared->latest_seq=2;
    next();command("power_arm","{\"count\":120}");assert(response().kind==255);
    next();command("power_scan","{\"count\":19}");assert(response().kind==255);
    next();command("power_scan","{\"count\":17}");assert(response().kind==4&&shared->control.scan_ms==17);
    next();command("power_load","{\"count\":2}");assert(response().kind==4&&shared->control.mode==2);
    const char *bad[]={"{\"count\":-1}","{\"count\":1000001}","{\"count\":1,\"count\":2}","{\"count\":1.5}","{\"mode\":1}"};
    for(unsigned i=0;i<5;i++){next();command("power_scan",bad[i]);assert(response().kind==255);}
    next();send_frame("{\"name\":\"power_status\",\"arguments\":{},}",77,0,0);assert(response().kind==255);
    next();command("telemetry","{}");assert(response().kind==255);
    /* Test actual TCP response ownership and delayed ACK for both replay modes. */
    m_runtime.phase=4;m_runtime.state=M_ACTIVE;m_runtime.t0=1000;m_runtime.t1=10000;m_test_ticks=2000;
    next();send_frame("{\"name\":\"replay_compact\",\"arguments\":{}}",41,1,0);
    assert(response().kind==2&&m_runtime.completed_compact==0&&m_runtime.pending_ack);
    struct tcp_pcb *pcb=fake_last_pcb();pcb->lastack=pcb->snd_lbb-1;
    assert(!pcb->sent_cb(pcb->callback_arg,pcb,1));assert(!m_runtime.completed_compact);
    fake_ack_all();assert(m_runtime.completed_compact==1);
    assert(shared->events[m_runtime.event_count-1].request_id==41);
    shared->control.mode=1;next();send_frame("{\"name\":\"replay_full\",\"arguments\":{}}",42,1,0);
    while(fake_wire_size()<20u+response().metadata_len+response().payload_len)fake_ack_all();
    assert(response().kind==1&&m_runtime.completed_full==0);
    assert(!memcmp(fake_wire()+20+response().metadata_len,e06_inference_input_data(),602112));
    fake_ack_all();assert(m_runtime.completed_full==1&&shared->events[m_runtime.event_count-1].request_id==42);
    shared->control.mode=2;next();send_frame("{\"name\":\"replay_compact\",\"arguments\":{}}",43,1,1);
    assert(response().kind==255&&(m_runtime.faults&M_FAULT_INPUT));
    m_runtime.faults=0;next();fake_inference_failure(1);
    send_frame("{\"name\":\"replay_compact\",\"arguments\":{}}",44,1,0);
    assert(response().kind==255&&(m_runtime.faults&M_FAULT_INFERENCE));
    m_runtime.state=M_DONE;next();command("power_export_events","{\"count\":0}");
    assert(response().kind==1&&response().payload_len==m_runtime.event_count*64);
    next();command("power_export_events","{\"count\":999999}");assert(response().kind==255);
    assert(fake_telemetry_calls()==0);
    assert(fatal_failure_cases(shared)==0);
    free(shared);puts("NETWORK_CONTROL_REPLAY_ACK_EXPORT_OK");return 0;
}
