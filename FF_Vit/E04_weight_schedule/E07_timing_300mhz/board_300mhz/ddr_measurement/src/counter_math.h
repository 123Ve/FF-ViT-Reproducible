#ifndef E07_DDR_COUNTER_MATH_H
#define E07_DDR_COUNTER_MATH_H
#include <stdint.h>
/* Valid when fewer than 2^32 events occur between snapshots. */
static inline uint32_t counter_delta(uint32_t before, uint32_t after) {
    return after - before;
}
#endif
