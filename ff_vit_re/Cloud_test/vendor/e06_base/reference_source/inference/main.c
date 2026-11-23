#include <stdint.h>
#include <stdio.h>

#include "ff.h"
#include "xaxidma.h"
#include "xaxipmon.h"
#include "xil_cache.h"
#include "xil_printf.h"
#include "xparameters.h"
#include "xstatus.h"
#include "xiltimer.h"
#include "xvit_block_top.h"

#include "weight_layout.h"

#define E06M_TP 2
#define E06M_TT (E06_T / E06M_TP)
#define E06M_WARMUP_FRAMES 2
#define E06M_REPETITIONS 10
#define E06M_FRAMES_PER_REPEAT 100
#define E06M_FRAME_TIMEOUT_TICKS ((uint64_t)COUNTS_PER_SECOND * 5ull)

enum {
    C_MM2S_REQ = 0, C_MM2S_BYTES, C_MM2S_LAT,
    C_S2MM_REQ, C_S2MM_BYTES, C_S2MM_LAT,
    C_WEIGHT_REQ, C_WEIGHT_BYTES, C_WEIGHT_LAT, C_WEIGHT_MAX_LAT
};

typedef struct {
    uint64_t total_start, total_end;
    uint64_t mm2s_start, mm2s_end;
    uint64_t s2mm_start, s2mm_end;
    uint64_t pl_start, pl_end;
} FrameTimes;

static BlockLayerWeights_C weights[E06_NUM_LAYERS] __attribute__((aligned(64)));
static int32_t raw_input[E06_T * E06_CI] __attribute__((aligned(64)));
static int16_t dma_input[E06_T * E06_CI] __attribute__((aligned(64)));
static int32_t dma_output[E06_NUM_CLASSES] __attribute__((aligned(64)));
static int32_t reference_output[E06_NUM_CLASSES] __attribute__((aligned(64)));
static FATFS fatfs;
static XAxiDma dma;
static XAxiPmon apm;
static XVit_block_top accelerator;

static uint64_t now_ticks(void) { XTime t; XTime_GetTime(&t); return (uint64_t)t; }
static uint64_t min64(uint64_t a, uint64_t b) { return a < b ? a : b; }
static uint64_t max64(uint64_t a, uint64_t b) { return a > b ? a : b; }
static uint64_t intersect(uint64_t a0, uint64_t a1, uint64_t b0, uint64_t b1) {
    uint64_t lo = max64(a0, b0), hi = min64(a1, b1);
    return hi > lo ? hi - lo : 0;
}

static int load_exact(const char *name, void *destination, UINT bytes) {
    FIL f; UINT total = 0;
    if (f_open(&f, name, FA_READ) != FR_OK) return XST_FAILURE;
    while (total < bytes) {
        UINT got = 0, request = bytes - total;
        if (request > (1u << 20)) request = 1u << 20;
        if (f_read(&f, (uint8_t *)destination + total, request, &got) != FR_OK || !got) {
            f_close(&f); return XST_FAILURE;
        }
        total += got;
    }
    f_close(&f); return XST_SUCCESS;
}

static int initialize_hardware(void) {
    XAxiDma_Config *dc = XAxiDma_LookupConfig(XPAR_XAXIDMA_0_BASEADDR);
    XVit_block_top_Config *vc = XVit_block_top_LookupConfig(XPAR_XVIT_BLOCK_TOP_0_BASEADDR);
    XAxiPmon_Config *pc = XAxiPmon_LookupConfig(XPAR_MEASUREMENT_APM_BASEADDR);
    if (!dc || !vc || !pc) return XST_FAILURE;
    if (XAxiDma_CfgInitialize(&dma, dc) != XST_SUCCESS || XAxiDma_HasSg(&dma)) return XST_FAILURE;
    xil_printf("DIAG_DMA_INIT_OK\r\n");
    if (XVit_block_top_CfgInitialize(&accelerator, vc) != XST_SUCCESS) return XST_FAILURE;
    xil_printf("DIAG_ACCEL_INIT_OK\r\n");
    xil_printf("DIAG_APM_INIT_BEGIN\r\n");
    if (XAxiPmon_CfgInitialize(&apm, pc, pc->BaseAddress) != XST_SUCCESS) return XST_FAILURE;
    xil_printf("DIAG_APM_INIT_OK\r\n");
    XAxiDma_IntrDisable(&dma, XAXIDMA_IRQ_ALL_MASK, XAXIDMA_DMA_TO_DEVICE);
    XAxiDma_IntrDisable(&dma, XAXIDMA_IRQ_ALL_MASK, XAXIDMA_DEVICE_TO_DMA);
    return XST_SUCCESS;
}

static int configure_apm(void) {
    const u8 slot[10] = {0,0,0,1,1,1,2,2,2,2};
    const u8 metric[10] = {
        XAPM_METRIC_SET_1, XAPM_METRIC_SET_3, XAPM_METRIC_SET_5,
        XAPM_METRIC_SET_0, XAPM_METRIC_SET_2, XAPM_METRIC_SET_6,
        XAPM_METRIC_SET_1, XAPM_METRIC_SET_3, XAPM_METRIC_SET_5,
        XAPM_METRIC_SET_15
    };
    for (u8 i = 0; i < 10; ++i)
        if (XAxiPmon_SetMetrics(&apm, slot[i], metric[i], i) != XST_SUCCESS) return XST_FAILURE;
    return XST_SUCCESS;
}

static int run_one_frame(FrameTimes *t) {
    const u32 tx_bytes = sizeof(dma_input), rx_bytes = sizeof(dma_output);
    int tx_done = 0, rx_done = 0, pl_done = 0;
    t->total_start = now_ticks();
    Xil_DCacheFlushRange((INTPTR)dma_input, tx_bytes);
    Xil_DCacheInvalidateRange((INTPTR)dma_output, rx_bytes);
    t->s2mm_start = now_ticks();
    if (XAxiDma_SimpleTransfer(&dma, (UINTPTR)dma_output, rx_bytes,
                               XAXIDMA_DEVICE_TO_DMA) != XST_SUCCESS) return XST_FAILURE;
    t->pl_start = now_ticks();
    XVit_block_top_Start(&accelerator);
    t->mm2s_start = now_ticks();
    if (XAxiDma_SimpleTransfer(&dma, (UINTPTR)dma_input, tx_bytes,
                               XAXIDMA_DMA_TO_DEVICE) != XST_SUCCESS) return XST_FAILURE;
    const uint64_t deadline = now_ticks() + E06M_FRAME_TIMEOUT_TICKS;
    while (!(tx_done && rx_done && pl_done)) {
        if (!tx_done && !XAxiDma_Busy(&dma, XAXIDMA_DMA_TO_DEVICE)) {
            t->mm2s_end = now_ticks(); tx_done = 1;
        }
        if (!rx_done && !XAxiDma_Busy(&dma, XAXIDMA_DEVICE_TO_DMA)) {
            t->s2mm_end = now_ticks(); rx_done = 1;
        }
        if (!pl_done && XVit_block_top_IsDone(&accelerator)) {
            t->pl_end = now_ticks(); pl_done = 1;
        }
        if (now_ticks() > deadline) {
            u32 tx_status = XAxiDma_ReadReg(dma.RegBase,
                XAXIDMA_TX_OFFSET + XAXIDMA_SR_OFFSET);
            u32 rx_status = XAxiDma_ReadReg(dma.RegBase,
                XAXIDMA_RX_OFFSET + XAXIDMA_SR_OFFSET);
            u32 accel_ctrl = XVit_block_top_ReadReg(accelerator.Control_BaseAddress,
                XVIT_BLOCK_TOP_CONTROL_ADDR_AP_CTRL);
            xil_printf("FRAME_TIMEOUT tx_done=%d rx_done=%d pl_done=%d\r\n",
                       tx_done, rx_done, pl_done);
            xil_printf("MM2S_STATUS=0x%08lx S2MM_STATUS=0x%08lx ACCEL_CTRL=0x%08lx\r\n",
                       (unsigned long)tx_status, (unsigned long)rx_status,
                       (unsigned long)accel_ctrl);
            return XST_FAILURE;
        }
    }
    Xil_DCacheInvalidateRange((INTPTR)dma_output, rx_bytes);
    t->total_end = now_ticks();
    return XST_SUCCESS;
}

static int verify_output(void) {
    int mismatches = 0;
    for (int i = 0; i < E06_NUM_CLASSES; ++i) {
        int v = dma_output[i] & 0x7ffff;
        if (v >= 262144) v -= 524288;
        if (v != reference_output[i]) ++mismatches;
    }
    return mismatches;
}

int main(void) {
    xil_printf("\r\nE06 passive DDR/PL overlap measurement\r\n");
    xil_printf("FRAME_OVERLAP=NO\r\n");
    xil_printf("INPUT_DDR_TO_PL_INCLUDED=YES\r\nPS_SCHEDULING_INCLUDED=YES\r\n");
    xil_printf("OUTPUT_DDR_AND_ACK_INCLUDED=YES\r\nSD_FILE_IO_INCLUDED=NO\r\n");
    xil_printf("SUSTAINED_DEFINITION=completed_serial_frames_per_total_measured_wall_time\r\n");
    xil_printf("INTERVAL_OVERLAP_SCOPE=command_to_polled_completion_not_DDR_beat_active_time\r\n");
    xil_printf("TIMER_HZ=%lu REPETITIONS=%d FRAMES_PER_REPEAT=%d\r\n",
               (unsigned long)COUNTS_PER_SECOND, E06M_REPETITIONS, E06M_FRAMES_PER_REPEAT);
    if (initialize_hardware() != XST_SUCCESS) {
        xil_printf("INIT_FAIL\r\n"); return XST_FAILURE;
    }
    xil_printf("DIAG_APM_CONFIG_BEGIN\r\n");
    if (configure_apm() != XST_SUCCESS) {
        xil_printf("APM_CONFIG_FAIL\r\n"); return XST_FAILURE;
    }
    xil_printf("DIAG_APM_CONFIG_OK\r\n");
    if (f_mount(&fatfs, "0:/", 1) != FR_OK) {
        xil_printf("SD_MOUNT_FAIL\r\n"); return XST_FAILURE;
    }
    xil_printf("DIAG_SD_MOUNT_OK\r\n");
    if (load_exact("weights.bin", weights, sizeof(weights)) != XST_SUCCESS ||
        load_exact("input.bin", raw_input, sizeof(raw_input)) != XST_SUCCESS ||
        load_exact("output.bin", reference_output, sizeof(reference_output)) != XST_SUCCESS) {
        xil_printf("INPUT_LOAD_FAIL\r\n"); return XST_FAILURE;
    }
    xil_printf("DIAG_INPUT_LOAD_OK\r\n");
    int p = 0;
    for (int tt = 0; tt < E06M_TT; ++tt) for (int c = 0; c < E06_CI; ++c)
        for (int tp = 0; tp < E06M_TP; ++tp)
            dma_input[p++] = (int16_t)raw_input[(tt * E06M_TP + tp) * E06_CI + c];
    Xil_DCacheFlushRange((INTPTR)weights, sizeof(weights));
    XVit_block_top_Set_ext_weights(&accelerator, (u64)(UINTPTR)weights);
    XVit_block_top_Set_num_layers(&accelerator, E06_NUM_LAYERS);
    FrameTimes t;
    for (int i = 0; i < E06M_WARMUP_FRAMES; ++i)
        if (run_one_frame(&t) != XST_SUCCESS) return XST_FAILURE;
    int mismatches = verify_output();
    xil_printf("BIT_EXACT_MISMATCHES=%d\r\n", mismatches);
    if (mismatches) return XST_FAILURE;

    xil_printf("MEASUREMENT_CSV_BEGIN\r\n");
    xil_printf("repeat,frames,total_ticks,pl_ticks,mm2s_ticks,s2mm_ticks,INTERVAL_OVERLAP_TICKS,"
               "MM2S_READ_REQUESTS,MM2S_READ_BYTES,MM2S_TOTAL_READ_LATENCY,"
               "S2MM_WRITE_REQUESTS,S2MM_WRITE_BYTES,S2MM_TOTAL_WRITE_LATENCY,"
               "WEIGHT_READ_REQUESTS,WEIGHT_READ_BYTES,WEIGHT_TOTAL_READ_LATENCY,WEIGHT_MAX_READ_LATENCY\r\n");
    for (int rep = 0; rep < E06M_REPETITIONS; ++rep) {
        uint64_t total=0, pl=0, tx=0, rx=0, overlap=0;
        XAxiPmon_DisableMetricsCounter(&apm); XAxiPmon_ResetMetricCounter(&apm);
        XAxiPmon_EnableMetricsCounter(&apm);
        for (int frame = 0; frame < E06M_FRAMES_PER_REPEAT; ++frame) {
            if (run_one_frame(&t) != XST_SUCCESS) return XST_FAILURE;
            total += t.total_end - t.total_start; pl += t.pl_end - t.pl_start;
            tx += t.mm2s_end - t.mm2s_start; rx += t.s2mm_end - t.s2mm_start;
            overlap += intersect(t.mm2s_start, t.mm2s_end, t.pl_start, t.pl_end);
            overlap += intersect(t.s2mm_start, t.s2mm_end, t.pl_start, t.pl_end);
        }
        XAxiPmon_DisableMetricsCounter(&apm);
        xil_printf("%d,%d,%llu,%llu,%llu,%llu,%llu", rep, E06M_FRAMES_PER_REPEAT,
            (unsigned long long)total, (unsigned long long)pl, (unsigned long long)tx,
            (unsigned long long)rx, (unsigned long long)overlap);
        for (int c = 0; c < 10; ++c) xil_printf(",%lu", (unsigned long)XAxiPmon_GetMetricCounter(&apm, c));
        xil_printf("\r\n");
    }
    xil_printf("MEASUREMENT_CSV_END\r\nBOARD_TEST_PASS\r\n");
    return XST_SUCCESS;
}
