/* Catches unbounded vendor-style receive polling, ignored NACK/TO, wrong FIFO setup. */
#include "bounded_i2c.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef struct {uint32_t cr,isr,size,address,tx[3];unsigned txcount,received;uint64_t tick;int busy,stuck,error;} fake;
static uint64_t tick(void *v){return ((fake *)v)->tick++;}
static uint32_t rd(void *v,uint32_t off){fake *f=v;
    if(off==0)return f->cr;
    if(off==4)return f->busy?256:((f->cr&1)&&f->received<2&&!f->stuck?32:0);
    if(off==16)return f->error?(uint32_t)f->error:f->stuck?0:f->isr;
    if(off==12)return f->received++?0xc0:0x00;
    return 0;
}
static void wr(void *v,uint32_t off,uint32_t x){fake *f=v;
    if(off==0)f->cr=x;
    if(off==16)f->isr&=~x;
    if(off==20)f->size=x;
    if(off==12){assert(f->txcount<3);f->tx[f->txcount++]=x;}
    if(off==8){f->address=x;f->isr=1;}
}
int main(void){fake f={0};m_register_io io={&f,rd,wr,tick,1000000};uint8_t data[3]={5,8,0};
    assert(m_i2c_transfer(&io,0x40,data,3,0)==0);
    assert(f.address==0x40&&f.txcount==3&&f.tx[0]==5&&f.tx[1]==8&&f.tx[2]==0);
    assert((f.cr&0x3f)==0x0e); /* master, 7bit, ACK, no HOLD or slave monitor */
    memset(&f,0,sizeof(f));assert(!m_i2c_transfer(&io,0x40,data,2,1));
    assert(data[0]==0&&data[1]==192&&f.size==2&&(f.cr&1));
    memset(&f,0,sizeof(f));f.stuck=1;assert(m_i2c_transfer(&io,0x40,data,2,1)!=0&&f.tick<3000);
    memset(&f,0,sizeof(f));f.busy=1;assert(m_i2c_transfer(&io,0x40,data,1,0)!=0&&f.tick<3000&&f.txcount==0);
    for(int error=4;error<=8;error+=4){memset(&f,0,sizeof(f));f.error=error;
        assert(m_i2c_transfer(&io,0x40,data,2,1)!=0);}
    puts("BOUNDED_MMIO_I2C_TIMEOUT_NACK_OK");return 0;
}
