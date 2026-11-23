#ifndef E06_TELEMETRY_H
#define E06_TELEMETRY_H
#include <stdint.h>
#include "e06_status.h"
typedef struct {
    uint64_t timestamp_ticks;
    int64_t monitored_power_uW;
    int32_t temperature_mC;
    uint8_t power_valid;
    uint8_t temperature_valid;
} e06_telemetry_t;
/* A sensor init error still permits sampling the surviving channel. */
int e06_telemetry_init(void);
/* Power requires all 18 rails. Invalid numeric fields are INT64_MIN/INT32_MIN.
 * The total covers monitored rails, not wall power. Single-owner API. */
int e06_telemetry_sample(e06_telemetry_t *out);
const char *e06_telemetry_last_error(void);
#endif
