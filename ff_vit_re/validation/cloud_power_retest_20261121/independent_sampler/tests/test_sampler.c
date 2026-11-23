#include "sampler.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
static uint64_t ticks;static int failure;static unsigned temperatures;
static uint64_t now(void *v){(void)v;return ticks++;}
static int sel(void *v,uint8_t d){(void)v;return d>1?-1:0;}
static int wr(void *v,uint8_t a,uint8_t r,uint16_t n){(void)v;(void)a;(void)r;(void)n;return 0;}
static int rd(void *v,uint8_t a,uint8_t r,uint16_t *n){
    (void)v;(void)a;if(failure)return -1;
    switch(r){case 0xfe:*n=0x5449;break;case 0xff:*n=0x2260;break;
        case 0:*n=0x4527;break;case 5:*n=2048;break;case 6:*n=8;break;default:*n=192;break;}return 0;
}
static int temp(uint32_t *r,int32_t *m){++temperatures;*r=30000;*m=42000;return 0;}
int main(void){
    m_shared *p=calloc(1,sizeof(*p));assert(p);m_service service;m_sampler sampler;
    m_io io={0,sel,rd,wr,now};m_service_init(&service,p,1000000,0,1);
    assert(m_sampler_init(&sampler,p,io,1,1000000,temp)==0);
    m_status status;assert(!m_status_read(p,&status)&&status.configured==0x3ffff);
    m_sampler_step(&sampler);assert(temperatures==1&&sampler.status.rail_count==0);
    unsigned publication=p->status_seq;m_sampler_step(&sampler);
    assert(p->status_seq==publication); /* do not saturate shared bus between 1ms heartbeats */
    p->control.phase=3;p->control.t0=2250000;p->control.t1=3250000;p->control.command=M_CMD_ARM;
    ++p->control.command_seq;ticks=1000000;m_sampler_step(&sampler);
    assert(sampler.status.phase==3&&sampler.status.state==M_GUARD&&sampler.status.rail_count==18);
    assert(!sampler.status.faults);
    ticks=2250000;m_sampler_step(&sampler);assert(sampler.status.state==M_ACTIVE);
    ticks=3250000;m_sampler_step(&sampler);assert(sampler.status.state==M_POST);
    ticks=4250000;m_sampler_step(&sampler);assert(sampler.status.state==M_DONE);
    unsigned saved=sampler.status.rail_count;ticks=5000000;m_sampler_step(&sampler);assert(sampler.status.rail_count==saved);
    p->control.command=M_CMD_RELEASE;++p->control.command_seq;m_sampler_step(&sampler);
    assert(sampler.status.state==M_IDLE&&sampler.status.rail_count==0);
    p->control.phase=4;p->control.t0=6000000;p->control.t1=7000000;p->control.command=M_CMD_ARM;++p->control.command_seq;
    ticks=5500000;failure=1;m_sampler_step(&sampler);
    assert(sampler.status.faults&M_FAULT_SENSOR);assert(sampler.status.invalid_samples==18);
    assert(sampler.status.faults&M_FAULT_HANDSHAKE); /* late arm leaves <1s preguard */
    assert(p->rails[0].power_uW==INT64_MIN&&p->rails[0].flags&M_I2C_ERROR);
    m_rail_record latest[18];assert(!m_latest_read(p,latest)&&latest[0].flags&M_I2C_ERROR);
    failure=0;ticks=5600000;m_sampler_step(&sampler);
    assert(!m_latest_read(p,latest)&&latest[0].flags&M_I2C_ERROR); /* first bad scan preserved */
    m_service_init(&service,p,1000000,0,2);
    assert(!m_sampler_init(&sampler,p,io,1,1000000,temp));
    p->control.phase=5;p->control.t0=9000100;p->control.t1=10000100;
    p->control.command=M_CMD_ARM;++p->control.command_seq;
    ticks=8000000;m_sampler_step(&sampler);
    /* Scheduled start is early enough, but later rails finish after cutoff. */
    assert(p->rails[0].end[3]<8000100&&p->rails[17].end[3]>8000100);
    assert(sampler.status.faults&M_FAULT_HANDSHAKE);
    failure=1;
    m_service_init(&service,p,1000000,0,3);
    assert(m_sampler_init(&sampler,p,io,1,1000000,temp)!=0);
    assert(sampler.status.faults&M_FAULT_CONFIG&&sampler.status.configured==0);
    free(p);puts("SAMPLER_GUARDS_CONTINUITY_FAULT_OK");return 0;
}
