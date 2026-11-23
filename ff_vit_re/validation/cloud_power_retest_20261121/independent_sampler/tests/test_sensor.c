/* Catches wrong INA226 fields, missing readback, unit scaling, stale/invalid-as-zero. */
#include "monitor.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef struct { uint16_t regs[2][16][256]; uint8_t domain; uint64_t tick;
    int fail_reg, corrupt_cal; unsigned selects; } fake;
static int select_domain(void *v,uint8_t d){fake *f=v;if(d>1)return -1;f->domain=d;++f->selects;return 0;}
static int read_reg(void *v,uint8_t a,uint8_t r,uint16_t *o){fake *f=v;if(r==f->fail_reg)return -1;*o=f->regs[f->domain][a-0x40][r];if(r==5&&f->corrupt_cal)*o=0;return 0;}
static int write_reg(void *v,uint8_t a,uint8_t r,uint16_t n){fake *f=v;f->regs[f->domain][a-0x40][r]=n;return 0;}
static uint64_t tick(void *v){return ++((fake*)v)->tick;}
int main(void){
    fake f={0};f.fail_reg=-1;
    m_io io={&f,select_domain,read_reg,write_reg,tick};
    const unsigned addresses[18]={0x40,0x41,0x42,0x43,0x44,0x45,0x46,0x47,0x4a,0x4b,0x40,0x41,0x42,0x43,0x44,0x45,0x46,0x47};
    for(unsigned r=0;r<18;r++){
        unsigned d=r<10?0:1,a=addresses[r]-0x40;
        f.regs[d][a][0xfe]=0x5449;f.regs[d][a][0xff]=0x2260;
        m_config_record c={0};assert(m_configure(&io,r,&c)==0);
        assert(c.config==0x4527&&c.calibration==2048&&c.flags==M_VALID);
        assert(f.regs[d][a][0]==0x4527&&f.regs[d][a][5]==2048);
        assert(m_rails[r].address==addresses[r]&&m_rails[r].domain==d);
        assert(m_rails[r].shunt_uohm==(r==10?2000u:5000u));
    }
    assert(m_power_uW(10,192)==6000000);assert(m_power_uW(0,192)==2400000);
    m_config_record c;f.corrupt_cal=1;assert(m_configure(&io,0,&c)!=0&&!(c.flags&M_VALID));f.corrupt_cal=0;
    f.regs[0][0][0xfe]=0;assert(m_configure(&io,0,&c)!=0);f.regs[0][0][0xfe]=0x5449;
    f.regs[1][0][1]=1200;f.regs[1][0][2]=800;f.regs[1][0][4]=4800;f.regs[1][0][3]=192;f.regs[1][0][6]=8;
    uint64_t fresh=0;m_rail_record row={0};assert(m_sample(&io,10,1000,&fresh,&row)==0);
    assert(row.power_uW==6000000&&row.flags==(M_VALID|M_FRESH)&&fresh>0);
    for(unsigned n=0;n<5;n++)assert(row.end[n]>row.begin[n]);
    assert(row.power==192&&row.current==4800&&row.bus==800&&row.shunt==1200);
    f.regs[1][0][6]=0;assert(m_sample(&io,10,1000,&fresh,&row)==0&&row.flags==M_VALID);
    f.tick+=151;assert(m_sample(&io,10,1000,&fresh,&row)!=0&&(row.flags&M_STALE));
    f.regs[1][0][6]=12;assert(m_sample(&io,10,1000,&fresh,&row)!=0&&(row.flags&M_OVERFLOW));
    assert(row.power_uW==INT64_MIN&&!(row.flags&M_VALID));
    f.regs[1][0][6]=8;f.regs[1][0][3]=65535;
    assert(m_sample(&io,10,1000,&fresh,&row)!=0&&(row.flags&M_SATURATED));
    f.regs[1][0][3]=192;f.fail_reg=3;
    assert(m_sample(&io,10,1000,&fresh,&row)!=0&&(row.flags&M_I2C_ERROR));
    assert(row.power_uW==INT64_MIN);
    f.fail_reg=-1;f.regs[1][0][1]=65534;
    assert(m_sample(&io,10,1000,&fresh,&row)!=0&&(row.flags&M_NEGATIVE)&&!(row.flags&M_SATURATED));
    puts("SENSOR_CONFIG_RAW_FRESHNESS_OK");return 0;
}
