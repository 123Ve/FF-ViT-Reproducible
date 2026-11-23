#include "e06_fake_bsp.h"
#include <assert.h>
#include <string.h>

FakeBsp fake;
static unsigned int domain, selected_register;
static int transfer_phase;
void fake_reset(void) {
    memset(&fake, 0, sizeof(fake));
    fake.dma_error_direction = fake.dma_busy_direction = fake.fail_rail = -1;
    fake.tick_step = 10;
    fake.file_sizes[0] = E06_BLOCK_WEIGHT_BYTES * E06_NUM_LAYERS;
    fake.file_sizes[1] = sizeof(fake.input);
    fake.file_sizes[2] = sizeof(fake.reference);
    fake.max_read = 65536;
    fake.temperature_raw = 30000;
    fake.temperature_C = 42.25f;
    for (size_t i = 0; i < E06_T * E06_CI; ++i) fake.input[i] = (int32_t)i;
    for (size_t i = 0; i < E06_NUM_CLASSES; ++i) {
        fake.logits[i] = 0x7fff6;
        fake.reference[i] = -10;
    }
    fake.logits[0] = 0x00000; fake.reference[0] = 0;
    fake.logits[1] = 0x3ffff; fake.reference[1] = 262143;
    fake.logits[2] = 0x40000; fake.reference[2] = -262144;
    fake.logits[3] = 0x7ffff; fake.reference[3] = -1;
    domain = selected_register = 0;
    transfer_phase = 0;
}
int f_mount(FATFS *fs, const char *path, int immediate) {
    (void)fs; assert(strcmp(path, "0:/") == 0 && immediate == 1);
    return fake.mount_error;
}
int f_open(FIL *file, const char *path, int mode) {
    assert(mode == FA_READ);
    if (strcmp(path, "weights.bin") == 0) file->kind = 0;
    else if (strcmp(path, "input.bin") == 0) file->kind = 1;
    else if (strcmp(path, "output.bin") == 0) file->kind = 2;
    else return 1;
    file->position = 0; file->size = fake.file_sizes[file->kind];
    return FR_OK;
}
size_t fake_f_size(const FIL *file) { return file->size; }
int f_read(FIL *file, void *destination, UINT bytes, UINT *got) {
    size_t count = file->size - file->position;
    if (count > bytes) count = bytes;
    if (count > fake.max_read) count = fake.max_read;
    *got = 0;
    if (fake.read_error) return 1;
    if (file->kind == 0) memset(destination, 0, count);
    else {
        const void *source = file->kind == 1 ? (const void *)fake.input : fake.reference;
        memcpy(destination, (const uint8_t *)source + file->position, count);
    }
    file->position += count; *got = (UINT)count;
    return FR_OK;
}
int f_close(FIL *file) { (void)file; return fake.close_error; }
void XTime_GetTime(XTime *ticks) { *ticks = fake.ticks; fake.ticks += fake.tick_step; }
void Xil_DCacheFlushRange(INTPTR address, u32 bytes) {
    assert(((uintptr_t)address & 63u) == 0);
    if (bytes == E06_BLOCK_WEIGHT_BYTES * E06_NUM_LAYERS) fake.weight_flushed = 1;
    else { assert(bytes == sizeof(fake.transmitted)); fake.flush_input = 1; }
}
void Xil_DCacheInvalidateRange(INTPTR address, u32 bytes) {
    assert(((uintptr_t)address & 63u) == 0 && bytes == sizeof(fake.logits));
    ++fake.invalidate_output;
}
XAxiDma_Config *XAxiDma_LookupConfig(UINTPTR address) {
    static XAxiDma_Config config; (void)address;
    return fake.hardware_error ? NULL : &config;
}
int XAxiDma_CfgInitialize(XAxiDma *dma, XAxiDma_Config *config) {
    (void)dma; (void)config; return 0;
}
int XAxiDma_HasSg(XAxiDma *dma) { (void)dma; return 0; }
void XAxiDma_IntrDisable(XAxiDma *dma, u32 mask, int direction) {
    (void)dma; (void)mask; (void)direction;
}
int XAxiDma_SimpleTransfer(XAxiDma *dma, UINTPTR address, u32 bytes, int direction) {
    (void)dma; ++fake.transfers;
    if (!fake.flush_input || !fake.invalidate_output) fake.cache_order_error = 1;
    if (direction == fake.dma_error_direction) return 1;
    if (direction == XAXIDMA_DEVICE_TO_DMA) {
        assert(transfer_phase == 0 && bytes == sizeof(fake.logits));
        memcpy((void *)address, fake.logits, bytes); transfer_phase = 1;
    } else {
        assert(transfer_phase == 2 && bytes == sizeof(fake.transmitted));
        memcpy(fake.transmitted, (const void *)address, bytes); transfer_phase = 0;
    }
    return 0;
}
int XAxiDma_Busy(XAxiDma *dma, int direction) {
    (void)dma; return direction == fake.dma_busy_direction;
}
XAxiPmon_Config *XAxiPmon_LookupConfig(UINTPTR address) {
    static XAxiPmon_Config config; (void)address; return &config;
}
int XAxiPmon_CfgInitialize(XAxiPmon *apm, XAxiPmon_Config *config, UINTPTR address) {
    (void)apm; (void)config; (void)address; return 0;
}
int XAxiPmon_SetMetrics(XAxiPmon *apm, u8 slot, u8 metric, u8 counter) {
    static const u8 slots[] = {0,0,0,1,1,1,2,2,2,2};
    static const u8 metrics[] = {1,3,5,0,2,6,1,3,5,15};
    (void)apm; assert(counter < 10 && slot == slots[counter] && metric == metrics[counter]);
    return fake.apm_error;
}
void XAxiPmon_DisableMetricsCounter(XAxiPmon *apm) { (void)apm; fake.metric_enabled = 0; }
void XAxiPmon_ResetMetricCounter(XAxiPmon *apm) { (void)apm; }
void XAxiPmon_EnableMetricsCounter(XAxiPmon *apm) { (void)apm; fake.metric_enabled = 1; }
XVit_block_top_Config *XVit_block_top_LookupConfig(UINTPTR address) {
    static XVit_block_top_Config config; (void)address; return &config;
}
int XVit_block_top_CfgInitialize(XVit_block_top *accel, XVit_block_top_Config *config) {
    (void)accel; (void)config; return 0;
}
void XVit_block_top_Set_ext_weights(XVit_block_top *accel, u64 address) {
    (void)accel; assert(fake.weight_flushed); fake.weight_address = address;
}
void XVit_block_top_Set_num_layers(XVit_block_top *accel, u32 count) {
    (void)accel; fake.layers = count;
}
void XVit_block_top_Start(XVit_block_top *accel) {
    (void)accel; assert(transfer_phase == 1); transfer_phase = 2; ++fake.starts;
}
u32 XVit_block_top_IsDone(XVit_block_top *accel) { (void)accel; return !fake.accelerator_stuck; }
XIicPs_Config *XIicPs_LookupConfig(UINTPTR address) {
    static XIicPs_Config config; (void)address; return &config;
}
int XIicPs_CfgInitialize(XIicPs *iic, XIicPs_Config *config, UINTPTR address) {
    (void)iic; (void)config; (void)address; return fake.iic_error;
}
int XIicPs_SelfTest(XIicPs *iic) { (void)iic; return fake.iic_error; }
int XIicPs_SetSClk(XIicPs *iic, u32 clock_hz) {
    (void)iic; assert(clock_hz == 400000); return fake.iic_error;
}
int XIicPs_BusIsBusy(XIicPs *iic) { (void)iic; return fake.bus_busy; }
int XIicPs_MasterSendPolled(XIicPs *iic, u8 *bytes, int count, uint16_t address) {
    (void)iic; assert(count == 1);
    if (fake.iic_error) return 1;
    if (address == 0x75) { assert(*bytes == 4 || *bytes == 5); domain = *bytes & 1u; }
    else selected_register = *bytes;
    return 0;
}
int XIicPs_MasterRecvPolled(XIicPs *iic, u8 *bytes, int count, uint16_t address) {
    unsigned int value, rail = domain == 1 ? 10u + address - 0x40u : address - 0x40u;
    (void)iic; assert(count == 2);
    if (domain == 0 && address >= 0x4a) rail -= 2;
    if (fake.iic_error || (int)rail == fake.fail_rail) return 1;
    switch (selected_register) {
    case 0xfe: value = fake.wrong_identity ? 0 : 0x5449; break;
    case 0xff: value = 0x2260; break;
    case 1: value = 4; break;
    case 2: value = 800; break;
    default: assert(0); return 1;
    }
    bytes[0] = (u8)(value >> 8); bytes[1] = (u8)value; return 0;
}
XSysMonPsu_Config *XSysMonPsu_LookupConfig(UINTPTR address) {
    static XSysMonPsu_Config config; (void)address;
    return fake.sysmon_error ? NULL : &config;
}
int XSysMonPsu_CfgInitialize(XSysMonPsu *sysmon, XSysMonPsu_Config *config, UINTPTR address) {
    (void)sysmon; (void)config; (void)address; return fake.sysmon_error;
}
uint16_t XSysMonPsu_GetAdcData(XSysMonPsu *sysmon, u8 channel, u8 bank) {
    (void)sysmon; assert(channel == XSM_CH_TEMP && bank == XSYSMON_PS);
    return fake.temperature_raw;
}
float XSysMonPsu_RawToTemperature_OnChip(uint16_t raw) {
    assert(raw == fake.temperature_raw); return fake.temperature_C;
}
