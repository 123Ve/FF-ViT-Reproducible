#include "platform.h"

#include "lwip/priv/tcp_priv.h"
#include "xil_cache.h"
#include "xiltimer.h"

static uint64_t last_tcp_ms;

void init_platform(void)
{
    /* This BSP has XTIMER_NO_TICK_TIMER=1. XTime is still available, but
     * XTimer_SetInterval/SetHandler would silently start no periodic tick.
     * Anchor TCP deadlines only when the network starts, after SD loading. */
}

void platform_enable_interrupts(void)
{
    /* GEM interrupt setup is owned by the SDT network adapter. */
}

void platform_start_network_timer(void)
{
    last_tcp_ms = get_time_ms();
}

void platform_poll_network_timer(void)
{
    uint64_t now = get_time_ms();
    while (now - last_tcp_ms >= TCP_TMR_INTERVAL) {
        last_tcp_ms += TCP_TMR_INTERVAL;
        /* Every 250 ms: fast timer, plus slow timer on alternate calls.
         * Keep advancing even after all application bytes were queued:
         * the final unacked segment still requires timeout retransmission. */
        tcp_tmr();
    }
}

void cleanup_platform(void)
{
    Xil_DCacheDisable();
    Xil_ICacheDisable();
}

uint64_t get_time_ms(void)
{
    XTime ticks;
    XTime_GetTime(&ticks);
    /* Split the conversion so ticks * 1000 cannot overflow on long runs. */
    return ((uint64_t)ticks / COUNTS_PER_SECOND) * 1000u
        + ((uint64_t)ticks % COUNTS_PER_SECOND) * 1000u / COUNTS_PER_SECOND;
}
