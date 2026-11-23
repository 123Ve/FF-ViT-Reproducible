#include "monitor.h"
#include "e06_inference.h"
#include "e06_network.h"
#include "net_config.h"
#include "platform.h"
#include "xil_printf.h"
m_service m_runtime;
int main(void){
    m_map_shared();
    m_service_init(&m_runtime,(m_shared *)(uintptr_t)M_SHARED_BASE,m_frequency(),m_core_id(),m_ticks());
    m_runtime.clock_ticks=m_ticks;
    init_platform();
    xil_printf("E07_INDEPENDENT_POWER_V1 CANDIDATE physical_status=NOT_RUN\r\n");
    xil_printf("FIRMWARE_SHA256=%s CORE=%u\r\n",E06_FIRMWARE_SHA256,m_core_id());
    if(m_core_id()!=0)return 1;
    if(e06_inference_init("0:/weights.bin","0:/input.bin","0:/output.bin")!=E06_OK){
        xil_printf("INFERENCE_INIT_FAIL=%s\r\n",e06_inference_last_error());return 2;
    }
    if(e06_network_start())return 3;
    for(;;){
        m_service_poll(&m_runtime,m_ticks());
        e06_network_poll();
        if(m_runtime.shared->control.mode==M_LOAD_CONTINUOUS&&m_runtime.state!=M_DONE&&!m_runtime.faults){
            e06_result_t result;uint64_t begin=m_ticks();
            int ok=e06_inference_run(&result)==E06_OK;uint64_t end=m_ticks();
            m_inference_event(&m_runtime,0,begin,end,result.mismatch_count,ok);
            if(!ok)m_runtime.shared->control.mode=M_LOAD_IDLE;
        }
    }
}
