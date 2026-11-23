/* Compatibility linkage only. Legacy telemetry command is rejected. No I2C. */
#include "e06_telemetry.h"
#include "monitor.h"
#include <string.h>
int e06_telemetry_init(void){return E06_OK;}
const char *e06_telemetry_last_error(void){return "use power_status and post-phase rail export";}
int e06_telemetry_sample(e06_telemetry_t *out){
    if(!out)return E06_ERR_ARGUMENT;
    memset(out,0,sizeof(*out));out->monitored_power_uW=INT64_MIN;out->temperature_mC=INT32_MIN;
    m_status s;if(m_status_read(m_runtime.shared,&s))return E06_ERR_SENSOR;
    out->temperature_mC=s.temperature_mC;out->temperature_valid=s.temperature_valid;
    out->timestamp_ticks=s.temperature_tick;return E06_ERR_SENSOR;
}
