#include "e06_inference.h"
#include <stddef.h>
#include <string.h>
#ifdef E06_HOST_TEST
#include "tests/fake_bsp/e06_fake_bsp.h"
#else
#include "ff.h"
#include "xaxidma.h"
#include "xaxipmon.h"
#include "xil_cache.h"
#include "xparameters.h"
#include "xstatus.h"
#include "xiltimer.h"
#include "xvit_block_top.h"
#endif
#include "weight_layout.h"

#define E06_TP 2
#define E06_TT (E06_T / E06_TP)
#define E06_FRAME_TIMEOUT_TICKS ((uint64_t)COUNTS_PER_SECOND * 5ull)

static BlockLayerWeights_C weights[E06_NUM_LAYERS] __attribute__((aligned(64)));
static int32_t raw_input[E06_T * E06_CI] __attribute__((aligned(64)));
static int16_t dma_input[E06_T * E06_CI] __attribute__((aligned(64)));
static int32_t dma_output[E06_NUM_CLASSES] __attribute__((aligned(64)));
static int32_t reference_output[E06_NUM_CLASSES] __attribute__((aligned(64)));
static FATFS fatfs;
static XAxiDma dma;
static XAxiPmon apm;
static XVit_block_top accelerator;
static int initialized;
static const char *last_error = "";

static int fail(int status, const char *message) { last_error = message; return status; }
const char *e06_inference_last_error(void) { return last_error; }
const void *e06_inference_input_data(void) { return initialized ? raw_input : NULL; }
size_t e06_inference_input_bytes(void) { return initialized ? sizeof(raw_input) : 0u; }
static uint64_t now_ticks(void) {
    XTime ticks;
    XTime_GetTime(&ticks);
    return (uint64_t)ticks;
}

static int load_exact(const char *path, void *destination, UINT bytes) {
    FIL file;
    UINT total = 0;
    if (f_open(&file, path, FA_READ) != FR_OK) return E06_ERR_IO;
    /* Reject both truncation and trailing bytes; never accept another layout. */
    if (f_size(&file) != bytes) { f_close(&file); return E06_ERR_IO; }
    while (total < bytes) {
        UINT got = 0, request = bytes - total;
        if (request > (1u << 20)) request = 1u << 20;
        if (f_read(&file, (uint8_t *)destination + total, request, &got) != FR_OK ||
            got == 0 || got > request) {
            f_close(&file);
            return E06_ERR_IO;
        }
        total += got;
    }
    return f_close(&file) == FR_OK ? E06_OK : E06_ERR_IO;
}

static int initialize_hardware(void) {
    XAxiDma_Config *dc = XAxiDma_LookupConfig(XPAR_XAXIDMA_0_BASEADDR);
    XVit_block_top_Config *vc = XVit_block_top_LookupConfig(XPAR_XVIT_BLOCK_TOP_0_BASEADDR);
    XAxiPmon_Config *pc = XAxiPmon_LookupConfig(XPAR_MEASUREMENT_APM_BASEADDR);
    const u8 slots[10] = {0,0,0,1,1,1,2,2,2,2};
    const u8 metrics[10] = {
        XAPM_METRIC_SET_1, XAPM_METRIC_SET_3, XAPM_METRIC_SET_5,
        XAPM_METRIC_SET_0, XAPM_METRIC_SET_2, XAPM_METRIC_SET_6,
        XAPM_METRIC_SET_1, XAPM_METRIC_SET_3, XAPM_METRIC_SET_5,
        XAPM_METRIC_SET_15
    };
    if (!dc || !vc || !pc) return E06_ERR_INIT;
    if (XAxiDma_CfgInitialize(&dma, dc) != XST_SUCCESS || XAxiDma_HasSg(&dma))
        return E06_ERR_INIT;
    if (XVit_block_top_CfgInitialize(&accelerator, vc) != XST_SUCCESS ||
        XAxiPmon_CfgInitialize(&apm, pc, pc->BaseAddress) != XST_SUCCESS)
        return E06_ERR_INIT;
    XAxiDma_IntrDisable(&dma, XAXIDMA_IRQ_ALL_MASK, XAXIDMA_DMA_TO_DEVICE);
    XAxiDma_IntrDisable(&dma, XAXIDMA_IRQ_ALL_MASK, XAXIDMA_DEVICE_TO_DMA);
    for (u8 i = 0; i < 10; ++i)
        if (XAxiPmon_SetMetrics(&apm, slots[i], metrics[i], i) != XST_SUCCESS)
            return E06_ERR_INIT;
    return E06_OK;
}

int e06_inference_init(const char *weights_path, const char *input_path,
                       const char *reference_path) {
    size_t position = 0;
    initialized = 0;
    if (!weights_path || !input_path || !reference_path)
        return fail(E06_ERR_ARGUMENT, "null artifact path");
    if (initialize_hardware() != E06_OK)
        return fail(E06_ERR_INIT, "DMA/APM/accelerator initialization failed");
    if (f_mount(&fatfs, "0:/", 1) != FR_OK)
        return fail(E06_ERR_IO, "SD mount failed");
    if (load_exact(weights_path, weights, sizeof(weights)) != E06_OK)
        return fail(E06_ERR_IO, "weights file read/size failed");
    if (load_exact(input_path, raw_input, sizeof(raw_input)) != E06_OK)
        return fail(E06_ERR_IO, "input file read/size failed");
    if (load_exact(reference_path, reference_output, sizeof(reference_output)) != E06_OK)
        return fail(E06_ERR_IO, "reference file read/size failed");
    for (int tt = 0; tt < E06_TT; ++tt)
        for (int channel = 0; channel < E06_CI; ++channel)
            for (int tp = 0; tp < E06_TP; ++tp)
                dma_input[position++] =
                    (int16_t)raw_input[(tt * E06_TP + tp) * E06_CI + channel];
    Xil_DCacheFlushRange((INTPTR)weights, sizeof(weights));
    XVit_block_top_Set_ext_weights(&accelerator, (u64)(UINTPTR)weights);
    XVit_block_top_Set_num_layers(&accelerator, E06_NUM_LAYERS);
    initialized = 1;
    last_error = "";
    return E06_OK;
}

static int frame_failure(int status, const char *message) {
    XAxiPmon_DisableMetricsCounter(&apm);
    /* A failed frame may leave transfers active. Do not reuse its buffers. */
    initialized = 0;
    return fail(status, message);
}

int e06_inference_run(e06_result_t *out) {
    uint64_t total_start, pl_start, mm2s_start, s2mm_start, poll_start;
    int tx_done = 0, rx_done = 0, pl_done = 0;
    if (!out) return fail(E06_ERR_ARGUMENT, "null inference result");
    memset(out, 0, sizeof(*out));
    out->predicted_class = -1;
    if (!initialized) return fail(E06_ERR_INIT, "inference is not initialized");
    XAxiPmon_DisableMetricsCounter(&apm);
    XAxiPmon_ResetMetricCounter(&apm);
    XAxiPmon_EnableMetricsCounter(&apm);
    total_start = now_ticks();
    Xil_DCacheFlushRange((INTPTR)dma_input, sizeof(dma_input));
    Xil_DCacheInvalidateRange((INTPTR)dma_output, sizeof(dma_output));
    s2mm_start = now_ticks();
    if (XAxiDma_SimpleTransfer(&dma, (UINTPTR)dma_output, sizeof(dma_output),
                               XAXIDMA_DEVICE_TO_DMA) != XST_SUCCESS)
        return frame_failure(E06_ERR_DMA, "S2MM transfer failed");
    pl_start = now_ticks();
    XVit_block_top_Start(&accelerator);
    mm2s_start = now_ticks();
    if (XAxiDma_SimpleTransfer(&dma, (UINTPTR)dma_input, sizeof(dma_input),
                               XAXIDMA_DMA_TO_DEVICE) != XST_SUCCESS)
        return frame_failure(E06_ERR_DMA, "MM2S transfer failed");
    poll_start = now_ticks();
    while (!(tx_done && rx_done && pl_done)) {
        if (!tx_done && !XAxiDma_Busy(&dma, XAXIDMA_DMA_TO_DEVICE)) {
            out->mm2s_ticks = now_ticks() - mm2s_start;
            tx_done = 1;
        }
        if (!rx_done && !XAxiDma_Busy(&dma, XAXIDMA_DEVICE_TO_DMA)) {
            out->s2mm_ticks = now_ticks() - s2mm_start;
            rx_done = 1;
        }
        if (!pl_done && XVit_block_top_IsDone(&accelerator)) {
            out->pl_ticks = now_ticks() - pl_start;
            pl_done = 1;
        }
        /* Elapsed subtraction also handles a wrapping tick counter. */
        if (now_ticks() - poll_start > E06_FRAME_TIMEOUT_TICKS)
            return frame_failure(E06_ERR_TIMEOUT, "DMA/accelerator frame timeout");
    }
    Xil_DCacheInvalidateRange((INTPTR)dma_output, sizeof(dma_output));
    out->total_ticks = now_ticks() - total_start;
    XAxiPmon_DisableMetricsCounter(&apm);
    for (int i = 0; i < E06_NUM_CLASSES; ++i) {
        int32_t value = (int32_t)((uint32_t)dma_output[i] & 0x7ffffu);
        if (value >= 262144) value -= 524288;
        dma_output[i] = value;
        if (value != reference_output[i]) ++out->mismatch_count;
        if (out->predicted_class < 0 || value > dma_output[out->predicted_class])
            out->predicted_class = i;
    }
    if (out->mismatch_count)
        return fail(E06_ERR_MISMATCH, "inference logits differ from exact reference");
    last_error = "";
    return E06_OK;
}
