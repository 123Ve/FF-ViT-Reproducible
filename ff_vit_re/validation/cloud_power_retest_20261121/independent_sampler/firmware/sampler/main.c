#include "sampler.h"
#include "firmware_build_identity.h"
/* Kept in both ELFs so the build checks bind both cores to the same candidate. */
const char sampler_identity[]=E06_FIRMWARE_SHA256;
int main(void){
    m_map_shared();m_shared *shared=(m_shared *)(uintptr_t)M_SHARED_BASE;
    while(__atomic_load_n(&shared->control.magic,__ATOMIC_ACQUIRE)!=M_MAGIC){}
    m_io io;int hardware=m_hardware_init(&io);m_sampler sampler;
    m_sampler_init(&sampler,shared,io,m_core_id(),m_frequency(),m_temperature_read);
    if(hardware)sampler.status.faults|=M_FAULT_CONFIG;
    for(;;){
        if(__atomic_load_n(&shared->control.magic,__ATOMIC_ACQUIRE)!=M_MAGIC)continue;
        /* A stale shared header must not permanently bind this core to an old
           service boot. The new epoch is acknowledged only after reconfigure. */
        if(sampler.status.epoch!=__atomic_load_n(&shared->control.epoch,__ATOMIC_ACQUIRE))
            m_sampler_init(&sampler,shared,io,m_core_id(),m_frequency(),m_temperature_read);
        m_sampler_step(&sampler);
    }
}
