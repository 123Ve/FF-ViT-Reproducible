#ifndef E06_LWIP_PLATFORM_H
#define E06_LWIP_PLATFORM_H

#include <stdint.h>

void init_platform(void);
void cleanup_platform(void);
void platform_enable_interrupts(void);
uint64_t get_time_ms(void);

#endif
