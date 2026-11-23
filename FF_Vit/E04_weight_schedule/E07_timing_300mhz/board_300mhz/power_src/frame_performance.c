#include "frame_performance.h"

int frame_performance(uint64_t ticks, uint32_t frames, uint32_t timer_hz,
                      uint64_t *average_ns, uint64_t *fps_milli) {
    if (!ticks || !frames || !timer_hz || !average_ns || !fps_milli) return 0;
    uint64_t rate_numerator = (uint64_t)frames * timer_hz;
    if (ticks > UINT64_MAX / 1000000000ull || rate_numerator > UINT64_MAX / 1000ull)
        return 0;
    *average_ns = (ticks * 1000000000ull) / rate_numerator;
    *fps_milli = (rate_numerator * 1000ull) / ticks;
    return 1;
}
