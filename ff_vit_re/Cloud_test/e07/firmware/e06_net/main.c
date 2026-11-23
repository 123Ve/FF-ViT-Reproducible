#include "e06_inference.h"
#include "e06_network.h"
#include "e06_telemetry.h"
#include "net_config.h"

#ifndef E06_HOST_TEST
#include "lwip/arch.h"
#endif
#include "platform.h"
#include "xil_printf.h"

int main(void)
{
    int status;
    init_platform();
#ifndef SDT
    platform_enable_interrupts();
#endif
    xil_printf("\r\nFVIT_BUILD_PHASE=%s\r\n", E06_STAGE);
    xil_printf("FVIT_MODEL=%s\r\n", E06_MODEL);
    xil_printf("FVIT_FIRMWARE_SHA256=%s\r\n", E06_FIRMWARE_SHA256);
    xil_printf("FVIT_WEIGHTS_SHA256=%s\r\n", E06_WEIGHTS_SHA256);
    status = e06_inference_init("0:/weights.bin", "0:/input.bin", "0:/output.bin");
    if (status != E06_OK) {
        xil_printf("INFERENCE_INIT_FAIL=%s\r\n", e06_inference_last_error());
        cleanup_platform();
        return status;
    }
    status = e06_telemetry_init();
    if (status != E06_OK)
        xil_printf("TELEMETRY_PARTIAL=%s\r\n", e06_telemetry_last_error());
    status = e06_network_start();
    if (status != 0) {
        xil_printf("NETWORK_INIT_FAIL=%d\r\n", status);
        cleanup_platform();
        return status;
    }
    xil_printf("NETWORK_READY IP=%s PORT=%u\r\n", E06_BOARD_IP_TEXT,
               (unsigned int)E06_TCP_PORT);
    for (;;) e06_network_poll();
}
