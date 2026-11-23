#ifndef E06_FAKE_BSP_H
#define E06_FAKE_BSP_H
#ifndef E06_HOST_TEST
#error "The fake BSP is host-test only"
#endif
#include <stddef.h>
#include <stdint.h>
#include "weight_layout.h"
typedef uint8_t u8;
typedef uint32_t u32;
typedef uint64_t u64;
typedef uintptr_t UINTPTR;
typedef intptr_t INTPTR;
typedef unsigned int UINT;
typedef uint64_t XTime;
typedef struct { int unused; } FATFS;
typedef struct { int kind; size_t position; size_t size; } FIL;
typedef struct { UINTPTR BaseAddress; } XAxiDma_Config;
typedef struct { UINTPTR BaseAddress; } XAxiPmon_Config;
typedef struct { UINTPTR BaseAddress; } XVit_block_top_Config;
typedef struct { UINTPTR BaseAddress; } XIicPs_Config;
typedef struct { UINTPTR BaseAddress; } XSysMonPsu_Config;
typedef struct { UINTPTR RegBase; } XAxiDma;
typedef struct { int unused; } XAxiPmon;
typedef struct { UINTPTR Control_BaseAddress; } XVit_block_top;
typedef struct { int unused; } XIicPs;
typedef struct { int unused; } XSysMonPsu;
#define XST_SUCCESS 0
#define XST_FAILURE 1
#define FR_OK 0
#define FA_READ 1
#define COUNTS_PER_SECOND 100u
#define XPAR_XAXIDMA_0_BASEADDR 1u
#define XPAR_XVIT_BLOCK_TOP_0_BASEADDR 2u
#define XPAR_MEASUREMENT_APM_BASEADDR 3u
#define XPAR_XIICPS_0_BASEADDR 4u
#define XPAR_XSYSMONPSU_0_BASEADDR 5u
#define XAXIDMA_DMA_TO_DEVICE 0
#define XAXIDMA_DEVICE_TO_DMA 1
#define XAXIDMA_IRQ_ALL_MASK 0xffffffffu
#define XAPM_METRIC_SET_0 0u
#define XAPM_METRIC_SET_1 1u
#define XAPM_METRIC_SET_2 2u
#define XAPM_METRIC_SET_3 3u
#define XAPM_METRIC_SET_5 5u
#define XAPM_METRIC_SET_6 6u
#define XAPM_METRIC_SET_15 15u
#define XSM_CH_TEMP 0u
#define XSYSMON_PS 0u

typedef struct {
    int mount_error, read_error, close_error, hardware_error, apm_error;
    int dma_error_direction, dma_busy_direction, accelerator_stuck;
    int iic_error, sysmon_error, fail_rail, wrong_identity, bus_busy;
    int transfers, starts, metric_enabled, cache_order_error;
    int flush_input, invalidate_output, weight_flushed;
    uint64_t ticks, tick_step, weight_address;
    unsigned int layers;
    size_t file_sizes[3], max_read;
    int32_t input[E06_T * E06_CI];
    int32_t reference[E06_NUM_CLASSES], logits[E06_NUM_CLASSES];
    int16_t transmitted[E06_T * E06_CI];
    uint16_t temperature_raw;
    float temperature_C;
} FakeBsp;
extern FakeBsp fake;
void fake_reset(void);
int f_mount(FATFS *, const char *, int);
int f_open(FIL *, const char *, int);
size_t fake_f_size(const FIL *);
#define f_size(file) fake_f_size(file)
int f_read(FIL *, void *, UINT, UINT *);
int f_close(FIL *);
void XTime_GetTime(XTime *);
void Xil_DCacheFlushRange(INTPTR, u32);
void Xil_DCacheInvalidateRange(INTPTR, u32);
XAxiDma_Config *XAxiDma_LookupConfig(UINTPTR);
int XAxiDma_CfgInitialize(XAxiDma *, XAxiDma_Config *);
int XAxiDma_HasSg(XAxiDma *);
void XAxiDma_IntrDisable(XAxiDma *, u32, int);
int XAxiDma_SimpleTransfer(XAxiDma *, UINTPTR, u32, int);
int XAxiDma_Busy(XAxiDma *, int);
XAxiPmon_Config *XAxiPmon_LookupConfig(UINTPTR);
int XAxiPmon_CfgInitialize(XAxiPmon *, XAxiPmon_Config *, UINTPTR);
int XAxiPmon_SetMetrics(XAxiPmon *, u8, u8, u8);
void XAxiPmon_DisableMetricsCounter(XAxiPmon *);
void XAxiPmon_ResetMetricCounter(XAxiPmon *);
void XAxiPmon_EnableMetricsCounter(XAxiPmon *);
XVit_block_top_Config *XVit_block_top_LookupConfig(UINTPTR);
int XVit_block_top_CfgInitialize(XVit_block_top *, XVit_block_top_Config *);
void XVit_block_top_Set_ext_weights(XVit_block_top *, u64);
void XVit_block_top_Set_num_layers(XVit_block_top *, u32);
void XVit_block_top_Start(XVit_block_top *);
u32 XVit_block_top_IsDone(XVit_block_top *);
XIicPs_Config *XIicPs_LookupConfig(UINTPTR);
int XIicPs_CfgInitialize(XIicPs *, XIicPs_Config *, UINTPTR);
int XIicPs_SelfTest(XIicPs *);
int XIicPs_SetSClk(XIicPs *, u32);
int XIicPs_BusIsBusy(XIicPs *);
int XIicPs_MasterSendPolled(XIicPs *, u8 *, int, uint16_t);
int XIicPs_MasterRecvPolled(XIicPs *, u8 *, int, uint16_t);
XSysMonPsu_Config *XSysMonPsu_LookupConfig(UINTPTR);
int XSysMonPsu_CfgInitialize(XSysMonPsu *, XSysMonPsu_Config *, UINTPTR);
uint16_t XSysMonPsu_GetAdcData(XSysMonPsu *, u8, u8);
float XSysMonPsu_RawToTemperature_OnChip(uint16_t);
#endif
