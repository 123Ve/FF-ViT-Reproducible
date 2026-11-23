#ifndef E07_GEM_TX_H
#define E07_GEM_TX_H
#include <stdint.h>
struct netif;
typedef struct {
    uint64_t last_poll_ms;
    uint64_t last_diagnostic_ms;
} e07_gem_tx_service_t;
/* Main-loop only. Uses the vendor completion reclaimer under IRQ protection. */
void e07_gem_tx_poll(e07_gem_tx_service_t *service, struct netif *netif,
                     uint64_t now_ms);
#endif
