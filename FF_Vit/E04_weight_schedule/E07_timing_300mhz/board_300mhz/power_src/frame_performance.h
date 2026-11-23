#ifndef E07_FRAME_PERFORMANCE_H
#define E07_FRAME_PERFORMANCE_H
#include <stdint.h>

/* Returns zero for invalid/overflowing data. FPS result is in milli-FPS. */
int frame_performance(uint64_t ticks, uint32_t frames, uint32_t timer_hz,
                      uint64_t *average_ns, uint64_t *fps_milli);
#endif
