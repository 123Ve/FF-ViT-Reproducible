#include <stdint.h>
#include <stdio.h>

#include "ff.h"
#include "xaxidma.h"
#include "xil_cache.h"
#include "xil_printf.h"
#include "xparameters.h"
#include "xstatus.h"
#include "xiltimer.h"
#include "xvit_block_top.h"

#include "weight_layout.h"

#define E07_TP 2
#define E07_TT (E07_T / E07_TP)
#define E07_WARMUP_FRAMES 2
#define E07_MEASURED_FRAMES 100

static BlockLayerWeights_C weights[E07_NUM_LAYERS] __attribute__((aligned(64)));
static int32_t raw_input[E07_T * E07_CI] __attribute__((aligned(64)));
static int16_t dma_input[E07_T * E07_CI] __attribute__((aligned(64)));
static int32_t dma_output[E07_NUM_CLASSES] __attribute__((aligned(64)));
static int32_t reference_output[E07_NUM_CLASSES] __attribute__((aligned(64)));

static FATFS fatfs;
static XAxiDma dma;
static XVit_block_top accelerator;

static int load_exact(const char *name, void *destination, UINT bytes) {
    FIL file;
    UINT total = 0;
    if (f_open(&file, name, FA_READ) != FR_OK) return XST_FAILURE;
    while (total < bytes) {
        UINT got = 0;
        UINT request = bytes - total;
        if (request > (1u << 20)) request = 1u << 20;
        if (f_read(&file, (uint8_t *)destination + total, request, &got) != FR_OK || got == 0) {
            f_close(&file);
            return XST_FAILURE;
        }
        total += got;
    }
    f_close(&file);
    return total == bytes ? XST_SUCCESS : XST_FAILURE;
}

static int initialize_hardware(void) {
    XAxiDma_Config *dma_cfg = XAxiDma_LookupConfig(XPAR_XAXIDMA_0_BASEADDR);
    XVit_block_top_Config *accel_cfg =
        XVit_block_top_LookupConfig(XPAR_XVIT_BLOCK_TOP_0_BASEADDR);
    if (dma_cfg == NULL || accel_cfg == NULL) return XST_FAILURE;
    if (XAxiDma_CfgInitialize(&dma, dma_cfg) != XST_SUCCESS) return XST_FAILURE;
    if (XAxiDma_HasSg(&dma)) return XST_FAILURE;
    XAxiDma_IntrDisable(&dma, XAXIDMA_IRQ_ALL_MASK, XAXIDMA_DMA_TO_DEVICE);
    XAxiDma_IntrDisable(&dma, XAXIDMA_IRQ_ALL_MASK, XAXIDMA_DEVICE_TO_DMA);
    return XVit_block_top_CfgInitialize(&accelerator, accel_cfg);
}

static int run_one_frame(void) {
    const u32 tx_bytes = sizeof(dma_input);
    const u32 rx_bytes = sizeof(dma_output);
    Xil_DCacheFlushRange((INTPTR)dma_input, tx_bytes);
    Xil_DCacheInvalidateRange((INTPTR)dma_output, rx_bytes);
    if (XAxiDma_SimpleTransfer(&dma, (UINTPTR)dma_output, rx_bytes,
                               XAXIDMA_DEVICE_TO_DMA) != XST_SUCCESS) return XST_FAILURE;
    XVit_block_top_Start(&accelerator);
    if (XAxiDma_SimpleTransfer(&dma, (UINTPTR)dma_input, tx_bytes,
                               XAXIDMA_DMA_TO_DEVICE) != XST_SUCCESS) return XST_FAILURE;
    while (XAxiDma_Busy(&dma, XAXIDMA_DMA_TO_DEVICE)) {}
    while (XAxiDma_Busy(&dma, XAXIDMA_DEVICE_TO_DMA)) {}
    while (!XVit_block_top_IsDone(&accelerator)) {}
    Xil_DCacheInvalidateRange((INTPTR)dma_output, rx_bytes);
    return XST_SUCCESS;
}

static int verify_output(void) {
    int mismatches = 0;
    for (int i = 0; i < E07_NUM_CLASSES; ++i) {
        int value = dma_output[i] & 0x7ffff;
        if (value >= 262144) value -= 524288;
        if (value != reference_output[i]) ++mismatches;
    }
    return mismatches;
}

int main(void) {
    xil_printf("\r\nE07 >=300-MHz timing-optimized board test\r\n");
    xil_printf("PL configured: 300.215099 MHz (MMCM; PS source 249.975021 MHz); timer Hz: %lu\r\n", (unsigned long)COUNTS_PER_SECOND);
    xil_printf("Block weight bytes: %lu; layers: %d\r\n",
               (unsigned long)sizeof(BlockLayerWeights_C), E07_NUM_LAYERS);

    if (initialize_hardware() != XST_SUCCESS || f_mount(&fatfs, "0:/", 1) != FR_OK) {
        xil_printf("INIT_FAIL\r\n");
        return XST_FAILURE;
    }
    if (load_exact("weights.bin", weights, sizeof(weights)) != XST_SUCCESS ||
        load_exact("input.bin", raw_input, sizeof(raw_input)) != XST_SUCCESS ||
        load_exact("output.bin", reference_output, sizeof(reference_output)) != XST_SUCCESS) {
        xil_printf("INPUT_LOAD_FAIL\r\n");
        return XST_FAILURE;
    }

    int position = 0;
    for (int tt = 0; tt < E07_TT; ++tt) {
        for (int channel = 0; channel < E07_CI; ++channel) {
            for (int tp = 0; tp < E07_TP; ++tp) {
                int token = tt * E07_TP + tp;
                dma_input[position++] = (int16_t)raw_input[token * E07_CI + channel];
            }
        }
    }

    Xil_DCacheFlushRange((INTPTR)weights, sizeof(weights));
    XVit_block_top_Set_ext_weights(&accelerator, (u64)(UINTPTR)weights);
    XVit_block_top_Set_num_layers(&accelerator, E07_NUM_LAYERS);

    for (int i = 0; i < E07_WARMUP_FRAMES; ++i) {
        if (run_one_frame() != XST_SUCCESS) return XST_FAILURE;
    }
    int mismatches = verify_output();
    xil_printf("BIT_EXACT_MISMATCHES=%d\r\n", mismatches);
    if (mismatches != 0) return XST_FAILURE;

    XTime start = 0;
    XTime end = 0;
    XTime_GetTime(&start);
    for (int i = 0; i < E07_MEASURED_FRAMES; ++i) {
        if (run_one_frame() != XST_SUCCESS) return XST_FAILURE;
    }
    XTime_GetTime(&end);

    const uint64_t ticks = (uint64_t)(end - start);
    const uint64_t ns_per_frame =
        (ticks * 1000000000ull) / ((uint64_t)COUNTS_PER_SECOND * E07_MEASURED_FRAMES);
    xil_printf("BOARD_TIMER_RAW_START=%llu\r\n", (unsigned long long)start);
    xil_printf("BOARD_TIMER_RAW_END=%llu\r\n", (unsigned long long)end);
    xil_printf("BOARD_TIMER_DELTA=%llu\r\n", (unsigned long long)ticks);
    xil_printf("MEASURED_FRAMES=%d\r\n", E07_MEASURED_FRAMES);
    xil_printf("AVERAGE_NS_PER_FRAME=%llu\r\n", (unsigned long long)ns_per_frame);
    xil_printf("BOARD_TEST_PASS\r\n");
    return XST_SUCCESS;
}
