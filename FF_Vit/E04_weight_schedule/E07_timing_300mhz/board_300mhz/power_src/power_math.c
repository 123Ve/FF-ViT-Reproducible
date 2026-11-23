#include "power_math.h"

int64_t ina226_bus_uV(uint16_t raw_bus) {
    return (int64_t)raw_bus * 1250;
}

int64_t ina226_current_uA(int16_t raw_shunt, uint32_t shunt_uohm) {
    if (shunt_uohm == 0u) return 0;
    return ((int64_t)raw_shunt * 2500 * 1000) / (int64_t)shunt_uohm;
}

int64_t ina226_power_uW(int64_t bus_uV, int64_t current_uA) {
    return (bus_uV * current_uA) / 1000000;
}
