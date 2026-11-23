/* PS-only observer. Frozen accepted E07 PL is reused without modification. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
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
#include "counter_math.h"

#define REPEATS 10
#define FRAMES 100
#define SNAPSHOT_FRAMES 10
#define COUNTERS 8
#define FRAME_TIMEOUT ((uint64_t)COUNTS_PER_SECOND * 5u)
/* Conservative guard on modulo snapshots, not an inferred DDR clock. */
#define SNAPSHOT_TIMEOUT ((uint64_t)COUNTS_PER_SECOND / 10u)

static BlockLayerWeights_C weights[E07_NUM_LAYERS] __attribute__((aligned(64)));
static int32_t raw_input[E07_T * E07_CI] __attribute__((aligned(64)));
static int16_t dma_input[E07_T * E07_CI] __attribute__((aligned(64)));
static int32_t dma_output[E07_NUM_CLASSES] __attribute__((aligned(64)));
static int32_t reference_output[E07_NUM_CLASSES] __attribute__((aligned(64)));
static FATFS fatfs;
static XAxiDma dma;
static XVit_block_top accelerator;
static XAxiPmon apm;
/* Slot 3: HP0 + DisplayPort. Slot 4: HP1 + HP2. No DisplayPort app is started. */
static const uint8_t slots[COUNTERS] = {3,3,4,4,3,3,4,4};
static const uint8_t metrics[COUNTERS] = {3,2,3,2,1,0,1,0};
static uint64_t idle_bytes;
static struct Result {
    uint64_t frame_ticks, window_ticks, counts[COUNTERS];
    unsigned mismatches;
} results[REPEATS];
static uint64_t baseline_ticks[REPEATS];

static uint64_t now(void) {
    XTime value;
    XTime_GetTime(&value);
    return (uint64_t)value;
}

static int load_exact(const char *name, void *destination, UINT bytes) {
    FIL file;
    UINT total = 0;
    FRESULT status = f_open(&file, name, FA_READ);
    if (status != FR_OK) {
        xil_printf("FILE_OPEN_FAIL name=%s fr=%d\r\n", name, (int)status);
        return XST_FAILURE;
    }
    if (f_size(&file) != bytes) {
        xil_printf("FILE_SIZE_FAIL name=%s got=%lu expected=%lu\r\n", name,
                   (unsigned long)f_size(&file), (unsigned long)bytes);
        f_close(&file);
        return XST_FAILURE;
    }
    while (total < bytes) {
        UINT got = 0, request = bytes - total;
        if (request > (1u << 20)) request = 1u << 20;
        status = f_read(&file, (uint8_t *)destination + total, request, &got);
        if (status != FR_OK || got == 0) {
            xil_printf("FILE_READ_FAIL name=%s fr=%d offset=%lu\r\n", name,
                       (int)status, (unsigned long)total);
            f_close(&file);
            return XST_FAILURE;
        }
        total += got;
    }
    return f_close(&file) == FR_OK ? XST_SUCCESS : XST_FAILURE;
}

static int initialize_hardware(void) {
    XAxiDma_Config *dc = XAxiDma_LookupConfig(XPAR_XAXIDMA_0_BASEADDR);
    XVit_block_top_Config *ac = XVit_block_top_LookupConfig(XPAR_XVIT_BLOCK_TOP_0_BASEADDR);
    if (!dc || !ac || XAxiDma_CfgInitialize(&dma, dc) != XST_SUCCESS ||
        XAxiDma_HasSg(&dma)) return XST_FAILURE;
    XAxiDma_IntrDisable(&dma, XAXIDMA_IRQ_ALL_MASK, XAXIDMA_DMA_TO_DEVICE);
    XAxiDma_IntrDisable(&dma, XAXIDMA_IRQ_ALL_MASK, XAXIDMA_DEVICE_TO_DMA);
    if (XVit_block_top_CfgInitialize(&accelerator, ac) != XST_SUCCESS) return XST_FAILURE;
    xil_printf("DIAG_DMA_ACCEL_INIT_OK\r\nDIAG_PS_DDR_APM_INIT_BEGIN\r\n");
    XAxiPmon_Config *pc = XAxiPmon_LookupConfig(XPAR_PERF_MONITOR_DDR_BASEADDR);
    if (!pc || pc->NumberofSlots != 6 || pc->NumberofCounters < COUNTERS ||
        pc->ScaleFactor != 1 || !pc->ModeAdvanced) {
        xil_printf("DDR_APM_CONFIG_UNSUPPORTED\r\n");
        return XST_FAILURE;
    }
    if (XAxiPmon_CfgInitialize(&apm, pc, pc->BaseAddress) != XST_SUCCESS) return XST_FAILURE;
    /* Disable filters, logging, sample timer and reset-on-sample-read. */
    XAxiPmon_WriteReg(pc->BaseAddress, XAPM_CTL_OFFSET, 0);
    XAxiPmon_WriteReg(pc->BaseAddress, XAPM_SICR_OFFSET, 0);
    for (unsigned i = 0; i < COUNTERS; ++i) {
        uint8_t m = 255, s = 255;
        if (XAxiPmon_SetMetrics(&apm, slots[i], metrics[i], i) != XST_SUCCESS ||
            XAxiPmon_GetMetrics(&apm, i, &m, &s) != XST_SUCCESS ||
            m != metrics[i] || s != slots[i]) {
            xil_printf("DDR_APM_SELECTOR_FAIL counter=%lu\r\n", (unsigned long)i);
            return XST_FAILURE;
        }
    }
    xil_printf("DIAG_PS_DDR_APM_CONFIG_OK BASE=0x%lx SCALE=1 MSR0=0x%lx MSR1=0x%lx\r\n",
               (unsigned long)pc->BaseAddress,
               (unsigned long)XAxiPmon_ReadReg(pc->BaseAddress, XAPM_MSR0_OFFSET),
               (unsigned long)XAxiPmon_ReadReg(pc->BaseAddress, XAPM_MSR1_OFFSET));
    return XST_SUCCESS;
}

static int run_one_frame(void) {
    Xil_DCacheFlushRange((INTPTR)dma_input, sizeof(dma_input));
    Xil_DCacheInvalidateRange((INTPTR)dma_output, sizeof(dma_output));
    const uint64_t started = now();
    if (XAxiDma_SimpleTransfer(&dma, (UINTPTR)dma_output, sizeof(dma_output),
                              XAXIDMA_DEVICE_TO_DMA) != XST_SUCCESS) return XST_FAILURE;
    XVit_block_top_Start(&accelerator);
    if (XAxiDma_SimpleTransfer(&dma, (UINTPTR)dma_input, sizeof(dma_input),
                              XAXIDMA_DMA_TO_DEVICE) != XST_SUCCESS) return XST_FAILURE;
    /* Retain serial completion ordering of the accepted E07 application. */
    while (XAxiDma_Busy(&dma, XAXIDMA_DMA_TO_DEVICE)) {
        if (now() - started > FRAME_TIMEOUT) goto timeout;
    }
    while (XAxiDma_Busy(&dma, XAXIDMA_DEVICE_TO_DMA)) {
        if (now() - started > FRAME_TIMEOUT) goto timeout;
    }
    while (!XVit_block_top_IsDone(&accelerator)) {
        if (now() - started > FRAME_TIMEOUT) goto timeout;
    }
    Xil_DCacheInvalidateRange((INTPTR)dma_output, sizeof(dma_output));
    return XST_SUCCESS;
timeout:
    xil_printf("FRAME_TIMEOUT TX_SR=0x%lx RX_SR=0x%lx\r\n",
        (unsigned long)XAxiDma_ReadReg(dma.RegBase, XAXIDMA_TX_OFFSET + XAXIDMA_SR_OFFSET),
        (unsigned long)XAxiDma_ReadReg(dma.RegBase, XAXIDMA_RX_OFFSET + XAXIDMA_SR_OFFSET));
    return XST_FAILURE;
}

static unsigned verify_output(void) {
    unsigned mismatches = 0;
    for (int i = 0; i < E07_NUM_CLASSES; ++i) {
        int value = dma_output[i] & 0x7ffff;
        if (value >= 262144) value -= 524288;
        if (value != reference_output[i]) ++mismatches;
    }
    return mismatches;
}

static void snapshot(uint32_t values[COUNTERS]) {
    for (unsigned i = 0; i < COUNTERS; ++i) values[i] = XAxiPmon_GetMetricCounter(&apm, i);
}

static int measure_idle(void) {
    uint32_t before[COUNTERS], after[COUNTERS];
    XAxiPmon_EnableMetricsCounter(&apm);
    snapshot(before);
    uint64_t start = now();
    while (now() - start < (uint64_t)COUNTS_PER_SECOND / 10u) {}
    XAxiPmon_DisableMetricsCounter(&apm);
    snapshot(after);
    for (unsigned i = 0; i < 4; ++i) idle_bytes += counter_delta(before[i], after[i]);
    xil_printf("IDLE_SHARED_PORT_BYTES=%llu\r\n", (unsigned long long)idle_bytes);
    if (idle_bytes) {
        xil_printf("DDR_SHARED_PORT_NOT_QUIET attribution_requires_investigation\r\n");
        return XST_FAILURE;
    }
    return XST_SUCCESS;
}

static int measure_repeat(struct Result *r) {
    uint32_t before[COUNTERS], after[COUNTERS];
    uint64_t window_start = now();
    XAxiPmon_EnableMetricsCounter(&apm);
    snapshot(before);
    for (unsigned chunk = 0; chunk < FRAMES / SNAPSHOT_FRAMES; ++chunk) {
        uint64_t start = now();
        for (unsigned frame = 0; frame < SNAPSHOT_FRAMES; ++frame) {
            if (run_one_frame() != XST_SUCCESS) {
                XAxiPmon_DisableMetricsCounter(&apm);
                return XST_FAILURE;
            }
        }
        uint64_t elapsed = now() - start;
        r->frame_ticks += elapsed;
        if (elapsed >= SNAPSHOT_TIMEOUT) {
            XAxiPmon_DisableMetricsCounter(&apm);
            xil_printf("DDR_SNAPSHOT_TOO_LONG cannot_guarantee_single_wrap\r\n");
            return XST_FAILURE;
        }
        /* Byte/request snapshots, no sample reset and no per-frame I/O. */
        snapshot(after);
        for (unsigned i = 0; i < COUNTERS; ++i) {
            r->counts[i] += counter_delta(before[i], after[i]);
            before[i] = after[i];
        }
    }
    XAxiPmon_DisableMetricsCounter(&apm);
    r->window_ticks = now() - window_start;
    r->mismatches = verify_output();
    return r->mismatches == 0 ? XST_SUCCESS : XST_FAILURE;
}

static const char *csv_header =
    "repeat,frames,frame_ticks,window_ticks,weight_read_bytes,weight_write_bytes,"
    "dma_read_bytes,dma_write_bytes,weight_read_requests,weight_write_requests,"
    "dma_read_requests,dma_write_requests,mismatches\r\n";

static void print_results(void) {
    xil_printf("BASELINE_CSV_BEGIN\r\nrepeat,frames,total_ticks,mismatches\r\n");
    for (unsigned i = 0; i < REPEATS; ++i)
        xil_printf("%lu,%d,%llu,0\r\n", (unsigned long)i, FRAMES,
                   (unsigned long long)baseline_ticks[i]);
    xil_printf("BASELINE_CSV_END\r\nDDR_CSV_BEGIN\r\n%s", csv_header);
    for (unsigned i = 0; i < REPEATS; ++i) {
        const struct Result *r = &results[i];
        xil_printf("%lu,%d,%llu,%llu", (unsigned long)i, FRAMES,
                   (unsigned long long)r->frame_ticks, (unsigned long long)r->window_ticks);
        for (unsigned j = 0; j < COUNTERS; ++j)
            xil_printf(",%llu", (unsigned long long)r->counts[j]);
        xil_printf(",%lu\r\n", (unsigned long)r->mismatches);
    }
    xil_printf("DDR_CSV_END\r\n");
}

static int save_results(void) {
    FIL file;
    UINT written;
    char row[384];
    if (f_open(&file, "0:/DDR_RAW.CSV", FA_CREATE_ALWAYS | FA_WRITE) != FR_OK) return XST_FAILURE;
    unsigned length = (unsigned)strlen(csv_header);
    if (f_write(&file, csv_header, length, &written) != FR_OK || written != length) goto fail;
    for (unsigned i = 0; i < REPEATS; ++i) {
        const struct Result *r = &results[i];
        int n = snprintf(row, sizeof(row), "%u,%d,%llu,%llu", i, FRAMES,
                         (unsigned long long)r->frame_ticks, (unsigned long long)r->window_ticks);
        for (unsigned j = 0; j < COUNTERS; ++j)
            n += snprintf(row+n, sizeof(row)-(unsigned)n, ",%llu", (unsigned long long)r->counts[j]);
        n += snprintf(row+n, sizeof(row)-(unsigned)n, ",%u\r\n", r->mismatches);
        if (n < 0 || (unsigned)n >= sizeof(row) ||
            f_write(&file, row, (UINT)n, &written) != FR_OK || written != (UINT)n) goto fail;
    }
    if (f_close(&file) != FR_OK) return XST_FAILURE;
    if (f_open(&file, "0:/DDR_META.TXT", FA_CREATE_ALWAYS | FA_WRITE) != FR_OK) return XST_FAILURE;
    int n = snprintf(row, sizeof(row),
        "IMAGE=E07_PS_DDR_APM_20261009\r\nTIMER_HZ=%llu\r\nIDLE_SHARED_PORT_BYTES=%llu\r\n"
        "REPETITIONS=10 FRAMES_PER_REPEAT=100\r\nSLOTS=3,4\r\nSCALE=1\r\n"
        "SCOPE=DDR_CONTROLLER_AXI_PORTS_NOT_DRAM_PINS_OR_ALL_PS_TRAFFIC\r\nDDR_TEST_PASS\r\n",
        (unsigned long long)COUNTS_PER_SECOND, (unsigned long long)idle_bytes);
    if (f_write(&file, row, (UINT)n, &written) != FR_OK || written != (UINT)n) goto fail;
    return f_close(&file) == FR_OK ? XST_SUCCESS : XST_FAILURE;
fail:
    f_close(&file);
    return XST_FAILURE;
}

int main(void) {
    xil_printf("\r\nE07 PS-only direct DDR APM measurement 20261009\r\n");
    xil_printf("PL_MHZ=300.215099 FRAME_OVERLAP=NO\r\nTIMER_HZ=%llu\r\n",
               (unsigned long long)COUNTS_PER_SECOND);
    xil_printf("SCOPE=DDR_CONTROLLER_AXI_PORTS_3_4_NOT_ALL_PS_TRAFFIC_NOT_DRAM_PINS\r\n"
               "SLOT3=HP0_WEIGHTS_SHARED_WITH_DISPLAYPORT\r\n"
               "SLOT4=HP1_DMA_SHARED_WITH_HP2\r\n"
               "SD_FILE_IO_INCLUDED=NO UART_INCLUDED=NO\r\n"
               "PS_SCHEDULING_CACHE_MAINTENANCE_INPUT_DMA_OUTPUT_DMA_ACK_INCLUDED=YES\r\n"
               "REPETITIONS=10 FRAMES_PER_REPEAT=100 SNAPSHOT_FRAMES=10\r\n");
    if (initialize_hardware() != XST_SUCCESS) goto fail;
    if (f_mount(&fatfs, "0:/", 1) != FR_OK) {
        xil_printf("SD_MOUNT_FAIL\r\n"); goto fail;
    }
    if (load_exact("0:/weights.bin", weights, sizeof(weights)) != XST_SUCCESS ||
        load_exact("0:/input.bin", raw_input, sizeof(raw_input)) != XST_SUCCESS ||
        load_exact("0:/output.bin", reference_output, sizeof(reference_output)) != XST_SUCCESS) goto fail;
    xil_printf("DIAG_INPUT_LOAD_OK\r\n");
    unsigned pos = 0;
    for (unsigned tt = 0; tt < E07_T / 2; ++tt)
        for (unsigned channel = 0; channel < E07_CI; ++channel)
            for (unsigned tp = 0; tp < 2; ++tp)
                dma_input[pos++] = (int16_t)raw_input[(tt*2+tp)*E07_CI+channel];
    Xil_DCacheFlushRange((INTPTR)weights, sizeof(weights));
    XVit_block_top_Set_ext_weights(&accelerator, (u64)(UINTPTR)weights);
    XVit_block_top_Set_num_layers(&accelerator, E07_NUM_LAYERS);
    for (unsigned i = 0; i < 2; ++i)
        if (run_one_frame() != XST_SUCCESS || verify_output() != 0) goto fail;
    xil_printf("BIT_EXACT_MISMATCHES=0\r\n");
    if (measure_idle() != XST_SUCCESS) goto fail;
    xil_printf("DIAG_BASELINE_BEGIN expect_about_3_seconds\r\n");
    for (unsigned rep = 0; rep < REPEATS; ++rep) {
        uint64_t start = now();
        for (unsigned frame = 0; frame < FRAMES; ++frame)
            if (run_one_frame() != XST_SUCCESS) goto fail;
        baseline_ticks[rep] = now() - start;
        if (verify_output() != 0) goto fail;
    }
    xil_printf("DIAG_DDR_MEASURE_BEGIN expect_about_3_seconds\r\n");
    for (unsigned rep = 0; rep < REPEATS; ++rep)
        if (measure_repeat(&results[rep]) != XST_SUCCESS) goto fail;
    print_results();
    /* A dead/filtered counter cannot be called a successful measurement. */
    for (unsigned rep = 0; rep < REPEATS; ++rep) {
        if (!results[rep].counts[0] || !results[rep].counts[2] || !results[rep].counts[3] ||
            !results[rep].counts[4] || !results[rep].counts[6] || !results[rep].counts[7]) {
            xil_printf("DDR_COUNTER_NO_ACTIVITY\r\n"); goto fail;
        }
    }
    if (save_results() != XST_SUCCESS) {
        xil_printf("SD_RESULT_SAVE_FAIL UART_RESULTS_AVAILABLE\r\n"); goto fail;
    }
    xil_printf("DDR_TEST_PASS files=DDR_RAW.CSV,DDR_META.TXT\r\n");
    return XST_SUCCESS;
fail:
    XAxiPmon_WriteReg(XPAR_PERF_MONITOR_DDR_BASEADDR, XAPM_CTL_OFFSET, 0);
    xil_printf("DDR_TEST_FAIL\r\n");
    return XST_FAILURE;
}
