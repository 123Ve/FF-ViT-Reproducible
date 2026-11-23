/* Real sensor/sampler behavior: a read-to-clear register is the I/O double. */
#include "sampler.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { uint16_t regs[18][256]; unsigned domain; uint64_t tick;
    int fail_bus, fail_rail, ready_on_power, backward;unsigned calls; } fake;
static uint64_t tick(void *v){
    fake *f=v;++f->calls;
    if(f->backward&&f->calls==3)f->tick-=100;
    if(f->backward&&f->calls==9)f->tick+=200;
    return ++f->tick;
}
static int select_domain(void *v,uint8_t d){((fake *)v)->domain=d;return 0;}
static unsigned rail_for(fake *f,uint8_t a){
    for(unsigned i=0;i<18;i++)if(m_rails[i].domain==f->domain&&m_rails[i].address==a)return i;
    abort();
}
static int read_reg(void *v,uint8_t a,uint8_t r,uint16_t *value){
    fake *f=v;unsigned i=rail_for(f,a);if((int)i==f->fail_rail||(i==7&&r==2&&f->fail_bus))return -1;
    *value=f->regs[i][r];
    if(r==6)f->regs[i][6]&=(uint16_t)~8u; /* Real CVRF read-to-clear behavior. */
    if(r==3&&f->ready_on_power){
        f->regs[i][6]|=8;f->regs[i][3]=192;f->ready_on_power=0;
    }
    return 0;
}
static int write_reg(void *v,uint8_t a,uint8_t r,uint16_t value){
    fake *f=v;unsigned i=rail_for(f,a);f->regs[i][r]=value;
    if(r==0)f->regs[i][6]&=(uint16_t)~8u;
    return 0;
}
static int temperature(uint32_t *raw,int32_t *mc){*raw=30000;*mc=42000;return 0;}
static void init(fake *f){
    memset(f,0,sizeof(*f));f->fail_rail=-1;f->tick=100;
    for(unsigned i=0;i<18;i++){
        f->regs[i][0xfe]=0x5449;f->regs[i][0xff]=0x2260;
        f->regs[i][1]=100;f->regs[i][2]=800;f->regs[i][4]=100;f->regs[i][3]=192;
    }
}
static m_io io_for(fake *f){return (m_io){f,select_domain,read_reg,write_reg,tick};}
static void sensor_case(const char *name){
    fake f;init(&f);m_io io=io_for(&f);m_rail_record row;uint64_t fresh=0;
    if(!strcmp(name,"pending")){
        f.regs[10][3]=0;f.ready_on_power=1;
        assert(m_sample(&io,10,1000000,&fresh,&row)>0);
        assert(!(row.flags&M_VALID)&&(row.flags&512u)&&fresh==0&&row.power_uW==INT64_MIN);
        assert(row.mask==0&&row.power==0);
        assert(m_sample(&io,10,1000000,&fresh,&row)==0);
        assert(row.flags==(M_VALID|M_FRESH)&&row.power_uW==6000000&&fresh>0);
        uint64_t observed=fresh;
        assert(m_sample(&io,10,1000000,&fresh,&row)==0);
        assert(row.flags==M_VALID&&fresh==observed); /* A held read is not another conversion. */
        f.tick+=150001;
        assert(m_sample(&io,10,1000000,&fresh,&row)<0&&(row.flags&M_STALE));
    }else if(!strcmp(name,"backward")){
        f.backward=1;f.regs[10][6]=8;
        assert(m_sample(&io,10,1000000,&fresh,&row)<0);
        assert(row.flags&M_CLOCK_ERROR&&!(row.flags&M_VALID)&&row.power_uW==INT64_MIN);
    }else if(!strcmp(name,"order")){
        f.regs[10][6]=8;assert(m_sample(&io,10,1000000,&fresh,&row)==0);
        assert(row.end[4]<=row.begin[0]&&row.end[4]<=row.begin[3]);
    }else{
        f.regs[7][6]=8;f.regs[7][1]=65534;f.regs[7][4]=65534;f.regs[7][3]=0;
        assert(m_sample(&io,7,1000000,&fresh,&row)<0);
        assert(row.shunt==65534&&row.current==65534&&(row.flags&M_NEGATIVE));
        assert(!(row.flags&M_SATURATED)&&!(row.flags&M_VALID)&&row.power_uW==INT64_MIN);
    }
}
static void sampler_case(const char *name){
    fake f;init(&f);m_io io=io_for(&f);m_shared *p=calloc(1,sizeof(*p));assert(p);
    m_service service;m_sampler sampler;m_service_init(&service,p,1000000,0,1);
    assert(m_sampler_init(&sampler,p,io,1,1000000,temperature)==0);
    uint64_t base=f.tick;m_rail_record rows[18];
    if(!strcmp(name,"profile-i2c")||!strcmp(name,"profile-other")||!strcmp(name,"profile-stale")){
        for(unsigned i=0;i<18;i++)f.regs[i][6]=8;
        int rail=!strcmp(name,"profile-other")?6:7;f.regs[rail][4]=65534;
        f.tick=base+10000;m_sampler_step(&sampler);
        if(rail==6){
            assert(!sampler.status.faults&&!sampler.status.invalid_samples);
            assert(sampler.status.included_negative_samples==1);
        }else{
            assert(!sampler.status.faults);
            if(!strcmp(name,"profile-i2c"))f.fail_bus=1;
            for(unsigned i=0;i<18;i++)if(i!=7)f.regs[i][6]=8;
            f.tick=base+(!strcmp(name,"profile-i2c")?40000:180000);m_sampler_step(&sampler);
            assert(sampler.status.invalid_samples==1&&!m_latest_read(p,rows));
            assert(rows[7].flags==(!strcmp(name,"profile-i2c")?260u:288u));
        }
    }else if(!strcmp(name,"profile")){
        for(unsigned i=0;i<18;i++)f.regs[i][6]=8;
        f.regs[7][1]=65534;f.regs[7][4]=65533;f.regs[7][3]=0;
        f.tick=base+120000;m_sampler_step(&sampler);
        assert(!m_latest_read(p,rows)&&rows[7].flags==258&&rows[7].power_uW==INT64_MIN);
        assert(rows[7].shunt==65534&&rows[7].current==65533);
        assert(sampler.status.conversion_ready==262015);
        #ifndef E07_PROFILE_RAILS
#define E07_PROFILE_RAILS 18
#endif
        if(E07_PROFILE_RAILS==17){
            assert(sampler.status.profile_rails==17);
            assert(sampler.status.observed_mask==262143&&sampler.status.excluded_negative_samples==1);
            assert(!sampler.status.faults&&!sampler.status.invalid_samples&&!sampler.diagnostic_frozen);
            f.tick=base+165000;m_sampler_step(&sampler);
            assert(!m_latest_read(p,rows)&&rows[7].flags==256&&!sampler.status.faults);
            f.regs[7][6]=12;f.tick=base+190000;m_sampler_step(&sampler);
            assert(!m_latest_read(p,rows)&&rows[7].flags==266&&sampler.diagnostic_frozen);
            assert(sampler.status.invalid_samples==1&&sampler.status.faults==M_FAULT_SENSOR);
            f.regs[7][6]=8;f.tick=base+220000;m_sampler_step(&sampler);
            assert(!m_latest_read(p,rows)&&rows[7].flags==266);
        }else assert(sampler.status.faults==M_FAULT_SENSOR&&sampler.diagnostic_frozen);
    }else if(!strcmp(name,"late-first")||!strcmp(name,"late-negative")){
        f.tick=base+140000;m_sampler_step(&sampler);assert(!sampler.status.faults);
        for(unsigned i=0;i<18;i++)f.regs[i][6]=8;
        if(!strcmp(name,"late-negative")){f.regs[7][1]=65534;f.regs[7][4]=65534;}
        f.tick=base+161000;m_sampler_step(&sampler);
        assert(sampler.status.faults&M_FAULT_SENSOR);
        assert(sampler.status.invalid_samples==18&&sampler.status.conversion_ready==0);
        assert(!m_latest_read(p,rows));
        for(unsigned i=0;i<18;i++)assert((rows[i].flags&M_STALE)&&!(rows[i].flags&M_VALID)&&rows[i].power_uW==INT64_MIN);
        if(!strcmp(name,"late-negative"))assert((rows[7].flags&M_NEGATIVE)&&rows[7].shunt==65534);
        f.tick=base+181100;m_sampler_step(&sampler); /* No new CVRF; held read must not qualify. */
        assert(sampler.status.conversion_ready==0&&sampler.status.invalid_samples==36);
    }else if(!strcmp(name,"timeout")){
        f.tick=base+151000;m_sampler_step(&sampler);
        assert(sampler.status.faults&M_FAULT_SENSOR);
        assert(sampler.status.invalid_samples==18&&sampler.status.stale_samples==18);
        assert(!m_latest_read(p,rows));
        for(unsigned i=0;i<18;i++)assert((rows[i].flags&512u)&&(rows[i].flags&M_STALE)&&!(rows[i].flags&M_VALID));
    }else{
        if(!strcmp(name,"pending-negative")){f.regs[7][1]=65534;f.regs[7][4]=65534;}
        f.tick=base+20000;m_sampler_step(&sampler);
        assert(!sampler.status.faults&&sampler.status.invalid_samples==0);
        assert(!m_latest_read(p,rows));
        for(unsigned i=0;i<18;i++)assert((rows[i].flags&512u)&&!(rows[i].flags&M_VALID));
        for(unsigned i=0;i<18;i++)f.regs[i][6]=8;
        f.tick=base+40000;m_sampler_step(&sampler);
        if(!strcmp(name,"pending-negative")){
            assert(sampler.status.faults&M_FAULT_SENSOR);
            assert(sampler.status.invalid_samples==1&&!m_latest_read(p,rows));
            assert(rows[7].flags&M_NEGATIVE&&rows[7].flags&M_FRESH&&rows[7].shunt==65534);
        }else{
            assert(!sampler.status.faults&&sampler.status.invalid_samples==0);
            assert(!m_latest_read(p,rows));
            for(unsigned i=0;i<18;i++)assert(rows[i].flags==(M_VALID|M_FRESH));
            f.fail_rail=7;f.tick=base+60000;m_sampler_step(&sampler);
            assert(sampler.status.invalid_samples==1&&!m_latest_read(p,rows));
            assert(rows[7].flags&M_I2C_ERROR);
            uint64_t frozen=rows[7].begin[0];f.fail_rail=-1;f.tick=base+80000;m_sampler_step(&sampler);
            assert(!m_latest_read(p,rows)&&rows[7].begin[0]==frozen&&(rows[7].flags&M_I2C_ERROR));
        }
    }
    free(p);
}
int main(int argc,char **argv){
    assert(argc==2);
    if(!strcmp(argv[1],"pending")||!strcmp(argv[1],"order")||!strcmp(argv[1],"negative")||!strcmp(argv[1],"backward"))sensor_case(argv[1]);
    else sampler_case(argv[1]);
    puts("FIRST_CONVERSION_AND_PRESERVED_FAULT_OK");return 0;
}
