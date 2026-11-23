#ifndef E06_POWER_MONITOR_H
#define E06_POWER_MONITOR_H

#include <stddef.h>
#include <stdint.h>

#include "xiicps.h"

#define INA226_MANUFACTURER_ID 0x5449u
#define INA226_DIE_ID 0x2260u

typedef enum {
    POWER_DOMAIN_PS = 0,
    POWER_DOMAIN_PL = 1,
} PowerDomain;

typedef struct {
    const char *rail;
    PowerDomain domain;
    uint8_t address;
    uint32_t shunt_uohm;
} PowerRail;

typedef struct {
    uint16_t bus_raw;
    int16_t shunt_raw;
    int64_t bus_uV;
    int64_t current_uA;
    int64_t power_uW;
} PowerReading;

extern const PowerRail e06_power_rails[];
extern const size_t e06_power_rail_count;

int power_monitor_initialize(XIicPs *iic);
int power_monitor_probe_all(XIicPs *iic);
int power_monitor_read(XIicPs *iic, const PowerRail *rail, PowerReading *reading);
const char *power_domain_name(PowerDomain domain);

#endif
