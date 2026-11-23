#include "monitor.h"
#include <string.h>
/* Mapping/Rshunt copied from Cloud_test/e07/firmware/e06_net/e06_telemetry.c. */
const m_rail m_rails[M_RAILS] = {
    {"VCCPSINTFP",0,0x40,5000},{"VCCPSINTLP",0,0x41,5000},
    {"VCCPSAUX",0,0x42,5000},{"VCCPSPLL",0,0x43,5000},
    {"MGTRAVCC",0,0x44,5000},{"MGTRAVTT",0,0x45,5000},
    {"VCCO_PSDDR_504",0,0x46,5000},{"VCCOPS",0,0x47,5000},
    {"VCCOPS3",0,0x4a,5000},{"VCCPSDDRPLL",0,0x4b,5000},
    {"VCCINT",1,0x40,2000},{"VCCBRAM",1,0x41,5000},
    {"VCCAUX",1,0x42,5000},{"VCC1V2",1,0x43,5000},
    {"VCC3V3",1,0x44,5000},{"VADJ_FMC",1,0x45,5000},
    {"MGTAVCC",1,0x46,5000},{"MGTAVTT",1,0x47,5000}
};
int m_configure(m_io *io,unsigned r,m_config_record *out) {
    if(!io||!out||r>=M_RAILS)return -1;
    memset(out,0,sizeof(*out));out->rail=r;out->begin=io->ticks(io->ctx);
    const m_rail *rail=&m_rails[r];
    int ok=io->select(io->ctx,rail->domain)==0 &&
        io->read(io->ctx,rail->address,0xfe,&out->manufacturer)==0 &&
        io->read(io->ctx,rail->address,0xff,&out->die)==0 &&
        out->manufacturer==0x5449 && (out->die&0xfff0)==0x2260 &&
        io->write(io->ctx,rail->address,5,M_CAL)==0 &&
        /* Configuration starts a new averaging sequence and clears CVRF.
           Calibration must already be installed for that first sequence. */
        io->write(io->ctx,rail->address,0,M_CONFIG)==0 &&
        io->read(io->ctx,rail->address,0,&out->config)==0 &&
        io->read(io->ctx,rail->address,5,&out->calibration)==0 &&
        out->config==M_CONFIG && out->calibration==M_CAL;
    out->end=io->ticks(io->ctx);out->flags=ok?M_VALID:M_CONFIG_ERROR;
    return ok?0:-1;
}
int64_t m_power_uW(unsigned r,uint16_t p) {
    if(r>=M_RAILS)return INT64_MIN;
    /* 25 * 0.00512/(2048 * R_ohm) W/code = 62500000/R_uohm uW/code. */
    return (int64_t)p*62500000/m_rails[r].shunt_uohm;
}
int m_sample(m_io *io,unsigned r,uint64_t hz,uint64_t *fresh,m_rail_record *out) {
    if(!io||!out||!fresh||r>=M_RAILS||!hz)return -1;
    static const uint8_t registers[5]={1,2,4,3,6};
    static const unsigned order[5]={4,0,1,2,3};
    uint16_t raw[5]={0};
    memset(out,0,sizeof(*out));out->rail=(uint16_t)r;
    out->config=M_CONFIG;out->calibration=M_CAL;out->power_uW=INT64_MIN;
    int selected=io->select(io->ctx,m_rails[r].domain)==0;
    /* Observe/clear conversion-ready before payload reads, not afterwards.
       Indices on the wire remain shunt,bus,current,Power,Mask. */
    for(unsigned k=0;k<5;k++) {
        unsigned n=order[k];
        out->begin[n]=io->ticks(io->ctx);
        if(!selected||io->read(io->ctx,m_rails[r].address,registers[n],&raw[n])!=0)
            out->flags|=M_I2C_ERROR;
        out->end[n]=io->ticks(io->ctx);
        if(out->end[n]<out->begin[n])out->flags|=M_CLOCK_ERROR;
        if(k&&out->begin[n]<out->end[order[k-1]])out->flags|=M_CLOCK_ERROR;
    }
    out->shunt=raw[0];out->bus=raw[1];out->current=raw[2];out->power=raw[3];out->mask=raw[4];
    if(raw[4]&4u)out->flags|=M_OVERFLOW;
    if(raw[0]==0x7fff||raw[0]==0x8000||raw[1]>=0x7fff||
       raw[2]==0x7fff||raw[2]==0x8000||raw[3]==0xffff)out->flags|=M_SATURATED;
    if((int16_t)raw[0]<0||(int16_t)raw[2]<0)out->flags|=M_NEGATIVE;
    if(!(out->flags&M_I2C_ERROR)&&(raw[4]&8u)) {
        out->flags|=M_FRESH;*fresh=out->end[4];
    }
    /* CVRF is a read-to-clear observation, never a conversion count.
       A signed negative affects power quality, not whether this ADC updated. */
    if(!*fresh) {
        out->flags|=M_NOT_READY;
        /* Preserve unqualified register contents, including signed flags.
           No conversion has yet licensed their use as measurements. */
        return out->flags&(M_I2C_ERROR|M_OVERFLOW|M_CLOCK_ERROR)?-1:1;
    }
    if(out->end[3]<*fresh||out->end[3]-*fresh>hz*150u/1000u)out->flags|=M_STALE;
    if(out->flags&~M_FRESH)return -1;
    out->flags|=M_VALID;out->power_uW=m_power_uW(r,raw[3]);return 0;
}
