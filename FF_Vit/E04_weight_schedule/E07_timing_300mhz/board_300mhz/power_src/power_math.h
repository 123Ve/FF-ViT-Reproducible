#ifndef E07_POWER_MATH_H
#define E07_POWER_MATH_H

#include <stdint.h>

int64_t ina226_bus_uV(uint16_t raw_bus);
int64_t ina226_current_uA(int16_t raw_shunt, uint32_t shunt_uohm);
int64_t ina226_power_uW(int64_t bus_uV, int64_t current_uA);

#endif
