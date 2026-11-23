#include "platform.h"

#include <stddef.h>

#include "lwip/tcp.h"
#include "xil_cache.h"
#include "xinterrupt_wrap.h"
#include "xiltimer.h"

volatile int TcpFastTmrFlag = 0;
volatile int TcpSlowTmrFlag = 0;
static volatile uint64_t tick_count;

static void timer_callback(void)
{
    static unsigned int fast_ticks;
    static unsigned int slow_ticks;
    ++tick_count;
    if (++fast_ticks == 5u) {
        TcpFastTmrFlag = 1;
        fast_ticks = 0u;
    }
    if (++slow_ticks == 10u) {
        TcpSlowTmrFlag = 1;
        slow_ticks = 0u;
    }
}

static void timer_handler(void *callback_ref, u32 timer_number)
{
    (void)callback_ref;
    (void)timer_number;
    timer_callback();
}

void init_platform(void)
{
    XTimer_SetInterval(50u);
    XTimer_SetHandler(timer_handler, NULL, XINTERRUPT_DEFAULT_PRIORITY);
}

void platform_enable_interrupts(void)
{
    /* SDT XTimer_SetHandler installs/enables the interrupt wrapper. */
}

void cleanup_platform(void)
{
    Xil_DCacheDisable();
    Xil_ICacheDisable();
}

uint64_t get_time_ms(void)
{
    return tick_count * 50u;
}
