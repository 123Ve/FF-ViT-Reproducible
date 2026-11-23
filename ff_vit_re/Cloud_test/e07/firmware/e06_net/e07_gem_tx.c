#include "e07_gem_tx.h"
#include "netif/xadapter.h"
#include "netif/xemacpsif.h"
#include "lwip/sys.h"
#include "xil_printf.h"

#define E07_GEM_POLL_MS 100u
#define E07_GEM_DIAGNOSTIC_MS 2000u

void e07_gem_tx_poll(e07_gem_tx_service_t *service, struct netif *netif,
                     uint64_t now_ms)
{
    struct xemac_s *adapter;
    xemacpsif_s *iface;
    XEmacPs_BdRing *ring;
    u32 before_hw, after_hw, before_free, after_free, before_bd, after_bd;
    u32 txsr, control;
    unsigned kicked = 0u;
    SYS_ARCH_DECL_PROTECT(level);

    if (service == NULL || netif == NULL || netif->state == NULL) return;
    if (now_ms - service->last_poll_ms < E07_GEM_POLL_MS) return;
    service->last_poll_ms = now_ms;
    adapter = (struct xemac_s *)netif->state;
    if (adapter->type != xemac_type_emacps || adapter->state == NULL) return;
    iface = (xemacpsif_s *)adapter->state;
    ring = &XEmacPs_GetTxRing(&iface->emacps);

    /* Same exclusion as the vendor's low_level_output: the TX interrupt and
     * the foreground must not simultaneously mutate the BD/pbuf ring. */
    SYS_ARCH_PROTECT(level);
    before_hw = ring->HwCnt;
    before_free = ring->FreeCnt;
    before_bd = before_hw ? XEmacPs_BdGetStatus(ring->HwHead) : 0u;
    txsr = XEmacPs_ReadReg(iface->emacps.Config.BaseAddress, XEMACPS_TXSR_OFFSET);
    control = XEmacPs_ReadReg(iface->emacps.Config.BaseAddress, XEMACPS_NWCTRL_OFFSET);
    if (before_hw != 0u) {
        /* Never edit pbuf refs/USED bits ourselves. The vendor routine only
         * releases complete packets marked USED by hardware. This also
         * covers a missing TX completion interrupt with no later traffic. */
        xemacps_process_sent_bds(iface, ring);
    }
    after_hw = ring->HwCnt;
    after_free = ring->FreeCnt;
    after_bd = after_hw ? XEmacPs_BdGetStatus(ring->HwHead) : 0u;
    /* Re-read after reclamation: DMA can progress while IRQs are masked.
     * A STARTTX write while already active is permitted by GEM, but only
     * request it for pending hardware-owned work on an enabled idle engine.
     * Do not reset TXEN, descriptors, queue base, or TCP state. */
    if (after_hw != 0u && !(after_bd & XEMACPS_TXBUF_USED_MASK)
            && (control & XEMACPS_NWCTRL_TXEN_MASK)
            && !(XEmacPs_ReadReg(iface->emacps.Config.BaseAddress,
                                XEMACPS_TXSR_OFFSET) & XEMACPS_TXSR_TXGO_MASK)) {
        dsb();
        XEmacPs_WriteReg(iface->emacps.Config.BaseAddress, XEMACPS_NWCTRL_OFFSET,
                         control | XEMACPS_NWCTRL_STARTTX_MASK);
        kicked = 1u;
    }
    SYS_ARCH_UNPROTECT(level);

    /* UART is outside the critical section and rate limited. Report the
     * pre-recovery register/BD snapshot, not a guessed cause of the stall. */
    if (before_hw != 0u
            && now_ms - service->last_diagnostic_ms >= E07_GEM_DIAGNOSTIC_MS) {
        service->last_diagnostic_ms = now_ms;
        xil_printf("GEM_TX_RECOVERY hw=%u->%u free=%u->%u bd=%x->%x "
                   "txsr=%x nwctrl=%x kick=%u\r\n",
                   (unsigned)before_hw, (unsigned)after_hw,
                   (unsigned)before_free, (unsigned)after_free,
                   (unsigned)before_bd, (unsigned)after_bd,
                   (unsigned)txsr, (unsigned)control, kicked);
    }
}
