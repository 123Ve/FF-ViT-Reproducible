#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "ff.h"
#include "xaxidma.h"
#include "xil_cache.h"
#include "xil_printf.h"
#include "xparameters.h"
#include "xstatus.h"
#include "xsysmonpsu.h"
#include "xiltimer.h"
#include "xvit_block_top.h"

#include "power_monitor.h"
#include "weight_layout.h"

#define E06_TP 2
#define E06_TT (E06_T / E06_TP)
#define E06_WARMUP_FRAMES 2
#define E06_POWER_REPEATS 10
#define E06_PHASE_SECONDS 30
#define E06_IDLE_SAMPLE_US 5000
#define E06_MAX_PHASE_SAMPLES 12000

typedef struct {
    uint64_t ticks;
    uint32_t sample_index;
    uint16_t rail_index;
    int32_t temperature_mC;
    PowerReading reading;
} LoggedSample;

static BlockLayerWeights_C weights[E06_NUM_LAYERS] __attribute__((aligned(64)));
static int32_t raw_input[E06_T * E06_CI] __attribute__((aligned(64)));
static int16_t dma_input[E06_T * E06_CI] __attribute__((aligned(64)));
static int32_t dma_output[E06_NUM_CLASSES] __attribute__((aligned(64)));
static int32_t reference_output[E06_NUM_CLASSES] __attribute__((aligned(64)));
static LoggedSample phase_samples[E06_MAX_PHASE_SAMPLES];

static FATFS fatfs;
static XAxiDma dma;
static XVit_block_top accelerator;
static XIicPs power_iic;
static XSysMonPsu sysmon;
static FIL raw_log;
static FIL phase_log;

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
    XSysMonPsu_Config *sysmon_cfg = XSysMonPsu_LookupConfig(XPAR_XSYSMONPSU_0_BASEADDR);
    if (dma_cfg == NULL || accel_cfg == NULL || sysmon_cfg == NULL) return XST_FAILURE;
    if (XAxiDma_CfgInitialize(&dma, dma_cfg) != XST_SUCCESS) return XST_FAILURE;
    if (XAxiDma_HasSg(&dma)) return XST_FAILURE;
    XAxiDma_IntrDisable(&dma, XAXIDMA_IRQ_ALL_MASK, XAXIDMA_DMA_TO_DEVICE);
    XAxiDma_IntrDisable(&dma, XAXIDMA_IRQ_ALL_MASK, XAXIDMA_DEVICE_TO_DMA);
    if (XVit_block_top_CfgInitialize(&accelerator, accel_cfg) != XST_SUCCESS)
        return XST_FAILURE;
    if (XSysMonPsu_CfgInitialize(&sysmon, sysmon_cfg, sysmon_cfg->BaseAddress) != XST_SUCCESS)
        return XST_FAILURE;
    return power_monitor_initialize(&power_iic);
}

static int start_one_frame(void) {
    const u32 tx_bytes = sizeof(dma_input);
    const u32 rx_bytes = sizeof(dma_output);
    Xil_DCacheFlushRange((INTPTR)dma_input, tx_bytes);
    Xil_DCacheInvalidateRange((INTPTR)dma_output, rx_bytes);
    if (XAxiDma_SimpleTransfer(&dma, (UINTPTR)dma_output, rx_bytes,
                               XAXIDMA_DEVICE_TO_DMA) != XST_SUCCESS)
        return XST_FAILURE;
    XVit_block_top_Start(&accelerator);
    return XAxiDma_SimpleTransfer(&dma, (UINTPTR)dma_input, tx_bytes,
                                  XAXIDMA_DMA_TO_DEVICE);
}

static int finish_one_frame(void) {
    while (XAxiDma_Busy(&dma, XAXIDMA_DMA_TO_DEVICE)) {}
    while (XAxiDma_Busy(&dma, XAXIDMA_DEVICE_TO_DMA)) {}
    while (!XVit_block_top_IsDone(&accelerator)) {}
    Xil_DCacheInvalidateRange((INTPTR)dma_output, sizeof(dma_output));
    return XST_SUCCESS;
}

static int run_one_frame(void) {
    if (start_one_frame() != XST_SUCCESS) return XST_FAILURE;
    return finish_one_frame();
}

static int verify_output(void) {
    int mismatches = 0;
    for (int i = 0; i < E06_NUM_CLASSES; ++i) {
        int value = dma_output[i] & 0x7ffff;
        if (value >= 262144) value -= 524288;
        if (value != reference_output[i]) ++mismatches;
    }
    return mismatches;
}

static int32_t read_temperature_mC(void) {
    uint16_t raw = XSysMonPsu_GetAdcData(&sysmon, XSM_CH_TEMP, XSYSMON_PS);
    float temperature = XSysMonPsu_RawToTemperature_OnChip(raw);
    return (int32_t)(temperature * 1000.0f);
}

static int collect_sample(uint32_t index, size_t rail_index, XTime phase_start) {
    LoggedSample *sample = &phase_samples[index];
    XTime now = 0;
    XTime_GetTime(&now);
    sample->ticks = (uint64_t)(now - phase_start);
    sample->sample_index = index;
    sample->rail_index = (uint16_t)rail_index;
    sample->temperature_mC = read_temperature_mC();
    return power_monitor_read(&power_iic, &e06_power_rails[rail_index], &sample->reading);
}

static int write_text(FIL *file, const char *text) {
    UINT written = 0;
    UINT bytes = (UINT)strlen(text);
    return f_write(file, text, bytes, &written) == FR_OK && written == bytes
               ? XST_SUCCESS
               : XST_FAILURE;
}

static int flush_samples(int repeat, const char *phase, uint32_t count) {
    char line[320];
    for (uint32_t index = 0; index < count; ++index) {
        const LoggedSample *sample = &phase_samples[index];
        const PowerRail *rail = &e06_power_rails[sample->rail_index];
        int length = snprintf(
            line, sizeof(line),
            "%d,%s,%llu,%lu,%s,%s,0x%02x,%lu,%u,%d,%lld,%lld,%lld,%ld\n",
            repeat, phase, (unsigned long long)sample->ticks,
            (unsigned long)sample->sample_index, power_domain_name(rail->domain),
            rail->rail, rail->address, (unsigned long)rail->shunt_uohm,
            sample->reading.bus_raw, sample->reading.shunt_raw,
            (long long)sample->reading.bus_uV,
            (long long)sample->reading.current_uA,
            (long long)sample->reading.power_uW,
            (long)sample->temperature_mC);
        if (length <= 0 || (size_t)length >= sizeof(line) || write_text(&raw_log, line) != XST_SUCCESS)
            return XST_FAILURE;
    }
    return f_sync(&raw_log) == FR_OK ? XST_SUCCESS : XST_FAILURE;
}

static int write_phase(int repeat, const char *phase, uint64_t ticks,
                       uint32_t samples, uint32_t frames, int mismatches) {
    char line[200];
    int length = snprintf(line, sizeof(line), "%d,%s,%llu,%lu,%lu,%d\n", repeat,
                          phase, (unsigned long long)ticks, (unsigned long)samples,
                          (unsigned long)frames, mismatches);
    if (length <= 0 || (size_t)length >= sizeof(line) ||
        write_text(&phase_log, line) != XST_SUCCESS)
        return XST_FAILURE;
    return f_sync(&phase_log) == FR_OK ? XST_SUCCESS : XST_FAILURE;
}

static void wait_sample_period(XTime sample_start) {
    const uint64_t wait_ticks = ((uint64_t)COUNTS_PER_SECOND * E06_IDLE_SAMPLE_US) / 1000000u;
    XTime now = 0;
    do {
        XTime_GetTime(&now);
    } while ((uint64_t)(now - sample_start) < wait_ticks);
}

static int measure_non_pl_phase(int repeat, const char *phase, int ps_active) {
    const uint64_t duration = (uint64_t)COUNTS_PER_SECOND * E06_PHASE_SECONDS;
    volatile uint32_t checksum = 0u;
    uint32_t samples = 0u;
    XTime start = 0;
    XTime now = 0;
    XTime_GetTime(&start);
    do {
        XTime sample_start = 0;
        XTime_GetTime(&sample_start);
        if (ps_active) {
            for (size_t i = 0; i < sizeof(dma_input) / sizeof(dma_input[0]); i += 64u)
                checksum = (checksum << 5) ^ (uint16_t)dma_input[i] ^ (checksum >> 2);
        }
        if (samples >= E06_MAX_PHASE_SAMPLES ||
            collect_sample(samples, samples % e06_power_rail_count, start) != XST_SUCCESS)
            return XST_FAILURE;
        ++samples;
        wait_sample_period(sample_start);
        XTime_GetTime(&now);
    } while ((uint64_t)(now - start) < duration);
    if (checksum == 0xffffffffu) xil_printf("CHECKSUM_SENTINEL\r\n");
    if (flush_samples(repeat, phase, samples) != XST_SUCCESS) return XST_FAILURE;
    return write_phase(repeat, phase, (uint64_t)(now - start), samples, 0u, 0);
}

static int measure_load_phase(int repeat) {
    static const char *phase = "FFVIT_SUSTAINED_LOAD";
    const uint64_t duration = (uint64_t)COUNTS_PER_SECOND * E06_PHASE_SECONDS;
    uint32_t samples = 0u;
    uint32_t frames = 0u;
    XTime start = 0;
    XTime now = 0;
    XTime_GetTime(&start);
    do {
        if (samples >= E06_MAX_PHASE_SAMPLES || start_one_frame() != XST_SUCCESS)
            return XST_FAILURE;
        if (collect_sample(samples, samples % e06_power_rail_count, start) != XST_SUCCESS)
            return XST_FAILURE;
        ++samples;
        if (finish_one_frame() != XST_SUCCESS) return XST_FAILURE;
        ++frames;
        XTime_GetTime(&now);
    } while ((uint64_t)(now - start) < duration);
    int mismatches = verify_output();
    if (flush_samples(repeat, phase, samples) != XST_SUCCESS) return XST_FAILURE;
    if (write_phase(repeat, phase, (uint64_t)(now - start), samples, frames, mismatches) != XST_SUCCESS)
        return XST_FAILURE;
    xil_printf("POWER_REPEAT=%d LOAD_FRAMES=%lu LOAD_TICKS=%llu MISMATCHES=%d\r\n",
               repeat, (unsigned long)frames, (unsigned long long)(now - start), mismatches);
    return mismatches == 0 ? XST_SUCCESS : XST_FAILURE;
}

static int create_logs(void) {
    if (f_open(&raw_log, "PWR_RAW.CSV", FA_CREATE_ALWAYS | FA_WRITE) != FR_OK)
        return XST_FAILURE;
    if (f_open(&phase_log, "PWR_PHS.CSV", FA_CREATE_ALWAYS | FA_WRITE) != FR_OK)
        return XST_FAILURE;
    if (write_text(&raw_log,
                   "repeat,phase,phase_ticks,sample_index,domain,rail,address,shunt_uohm,"
                   "bus_raw,shunt_raw,bus_uV,current_uA,power_uW,temperature_mC\n") != XST_SUCCESS)
        return XST_FAILURE;
    return write_text(&phase_log, "repeat,phase,ticks,samples,frames,mismatches\n");
}

int main(void) {
    static const char *idle_phase = "PL_CONFIGURED_IDLE";
    static const char *ps_phase = "PS_ACTIVE_NO_PL";
    xil_printf("\r\nE06 250-MHz reviewer power measurement image\r\n");
    xil_printf("POWER_SCOPE=ZCU102_INA226_MONITORED_RAILS_NOT_WALL_POWER\r\n");
    xil_printf("POWER_REPEATS=%d PHASE_SECONDS=%d\r\n", E06_POWER_REPEATS, E06_PHASE_SECONDS);
    xil_printf("TIMER_HZ=%lu FRAME_OVERLAP=NO\r\n", (unsigned long)COUNTS_PER_SECOND);

    if (initialize_hardware() != XST_SUCCESS || f_mount(&fatfs, "0:/", 1) != FR_OK) {
        xil_printf("INIT_FAIL\r\n");
        return XST_FAILURE;
    }
    if (power_monitor_probe_all(&power_iic) != XST_SUCCESS) {
        xil_printf("POWER_MONITOR_UNAVAILABLE\r\n");
        return XST_FAILURE;
    }
    if (load_exact("weights.bin", weights, sizeof(weights)) != XST_SUCCESS ||
        load_exact("input.bin", raw_input, sizeof(raw_input)) != XST_SUCCESS ||
        load_exact("output.bin", reference_output, sizeof(reference_output)) != XST_SUCCESS ||
        create_logs() != XST_SUCCESS) {
        xil_printf("INPUT_OR_LOG_INIT_FAIL\r\n");
        return XST_FAILURE;
    }

    int position = 0;
    for (int tt = 0; tt < E06_TT; ++tt) {
        for (int channel = 0; channel < E06_CI; ++channel) {
            for (int tp = 0; tp < E06_TP; ++tp) {
                int token = tt * E06_TP + tp;
                dma_input[position++] = (int16_t)raw_input[token * E06_CI + channel];
            }
        }
    }
    Xil_DCacheFlushRange((INTPTR)weights, sizeof(weights));
    XVit_block_top_Set_ext_weights(&accelerator, (u64)(UINTPTR)weights);
    XVit_block_top_Set_num_layers(&accelerator, E06_NUM_LAYERS);

    for (int i = 0; i < E06_WARMUP_FRAMES; ++i)
        if (run_one_frame() != XST_SUCCESS) return XST_FAILURE;
    if (verify_output() != 0) {
        xil_printf("BIT_EXACT_WARMUP_FAIL\r\n");
        return XST_FAILURE;
    }

    xil_printf("POWER_CSV_BEGIN\r\n");
    for (int repeat = 0; repeat < E06_POWER_REPEATS; ++repeat) {
        if (measure_non_pl_phase(repeat, idle_phase, 0) != XST_SUCCESS ||
            measure_non_pl_phase(repeat, ps_phase, 1) != XST_SUCCESS ||
            measure_load_phase(repeat) != XST_SUCCESS) {
            xil_printf("POWER_MEASUREMENT_FAIL repeat=%d\r\n", repeat);
            return XST_FAILURE;
        }
    }
    f_close(&raw_log);
    f_close(&phase_log);
    xil_printf("POWER_CSV_END\r\n");
    xil_printf("POWER_TEST_PASS files=PWR_RAW.CSV,PWR_PHS.CSV\r\n");
    return XST_SUCCESS;
}
