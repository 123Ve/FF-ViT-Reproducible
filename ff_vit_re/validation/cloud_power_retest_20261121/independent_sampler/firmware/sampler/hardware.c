#include "sampler.h"
#include "bounded_i2c.h"
#include "xiicps.h"
#include "xparameters.h"
#include "xsysmonpsu.h"
#include <math.h>
static XIicPs iic;
static XSysMonPsu sysmon;
static int initialized;
static uint64_t ticks(void *ctx){(void)ctx;return m_ticks();}
static uint32_t reg_read(void *ctx,uint32_t reg){(void)ctx;return XIicPs_ReadReg(iic.Config.BaseAddress,reg);}
static void reg_write(void *ctx,uint32_t reg,uint32_t value){(void)ctx;XIicPs_WriteReg(iic.Config.BaseAddress,reg,value);}
static m_register_io registers;
static int send(uint8_t address,uint8_t *data,int n){
    return initialized?m_i2c_transfer(&registers,address,data,(unsigned)n,0):-1;
}
static int select_domain(void *ctx,uint8_t domain){(void)ctx;uint8_t value=4u|domain;return send(0x75,&value,1);}
static int write_reg(void *ctx,uint8_t address,uint8_t reg,uint16_t value){
    (void)ctx;uint8_t bytes[3]={reg,(uint8_t)(value>>8),(uint8_t)value};return send(address,bytes,3);
}
static int read_reg(void *ctx,uint8_t address,uint8_t reg,uint16_t *value){
    (void)ctx;uint8_t bytes[2];
    if(send(address,&reg,1)||m_i2c_transfer(&registers,address,bytes,2,1))return -1;
    *value=((uint16_t)bytes[0]<<8)|bytes[1];return 0;
}
int m_hardware_init(m_io *io){
    *io=(m_io){0,select_domain,read_reg,write_reg,ticks};
    registers=(m_register_io){0,reg_read,reg_write,ticks,m_frequency()};
    XIicPs_Config *ic=XIicPs_LookupConfig(XPAR_XIICPS_0_BASEADDR);
    XSysMonPsu_Config *sc=XSysMonPsu_LookupConfig(XPAR_XSYSMONPSU_0_BASEADDR);
    initialized=ic&&sc&&XIicPs_CfgInitialize(&iic,ic,ic->BaseAddress)==XST_SUCCESS&&
        XIicPs_SelfTest(&iic)==XST_SUCCESS&&XIicPs_SetSClk(&iic,400000)==XST_SUCCESS&&
        XSysMonPsu_CfgInitialize(&sysmon,sc,sc->BaseAddress)==XST_SUCCESS;
    return initialized?0:-1;
}
int m_temperature_read(uint32_t *raw,int32_t *mc){
    if(!initialized)return -1;
    *raw=XSysMonPsu_GetAdcData(&sysmon,XSM_CH_TEMP,XSYSMON_PS);
    if(*raw==0||*raw==65535)return -1;
    float c=XSysMonPsu_RawToTemperature_OnChip(*raw);
    if(!isfinite(c)||c< -55||c>150)return -1;
    *mc=(int32_t)(c*1000);return 0;
}
