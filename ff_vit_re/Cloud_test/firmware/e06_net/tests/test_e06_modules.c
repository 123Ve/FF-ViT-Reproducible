#include "e06_inference.h"
#include "e06_telemetry.h"
#include "fake_bsp/e06_fake_bsp.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static int init_inference(void) {
    return e06_inference_init("weights.bin", "input.bin", "output.bin");
}
static void test_arguments_and_uninitialized(void) {
    e06_result_t result;
    e06_telemetry_t sample;
    assert(e06_inference_run(NULL) == E06_ERR_ARGUMENT);
    assert(e06_inference_run(&result) == E06_ERR_INIT);
    assert(e06_inference_input_data() == NULL);
    assert(e06_inference_input_bytes() == 0u);
    assert(strlen(e06_inference_last_error()) > 0);
    assert(e06_telemetry_sample(NULL) == E06_ERR_ARGUMENT);
    assert(e06_telemetry_sample(&sample) == E06_ERR_INIT);
    assert(sample.power_valid == 0 && sample.temperature_valid == 0);
    assert(strlen(e06_telemetry_last_error()) > 0);
    assert(e06_inference_init(NULL, "input.bin", "output.bin") == E06_ERR_ARGUMENT);
    assert(e06_inference_init("weights.bin", NULL, "output.bin") == E06_ERR_ARGUMENT);
    assert(e06_inference_init("weights.bin", "input.bin", NULL) == E06_ERR_ARGUMENT);
}
static void test_loading_and_init_errors(void) {
    e06_result_t result;
    for (int file = 0; file < 3; ++file) {
        fake_reset(); --fake.file_sizes[file];
        assert(init_inference() == E06_ERR_IO);
        assert(e06_inference_run(&result) == E06_ERR_INIT);
        fake_reset(); ++fake.file_sizes[file];
        assert(init_inference() == E06_ERR_IO);
    }
    fake_reset(); fake.mount_error = 1; assert(init_inference() == E06_ERR_IO);
    fake_reset(); fake.read_error = 1; assert(init_inference() == E06_ERR_IO);
    fake_reset(); fake.max_read = 0; assert(init_inference() == E06_ERR_IO);
    fake_reset(); fake.close_error = 1; assert(init_inference() == E06_ERR_IO);
    fake_reset(); fake.hardware_error = 1; assert(init_inference() == E06_ERR_INIT);
    fake_reset(); fake.apm_error = 1; assert(init_inference() == E06_ERR_INIT);
    fake_reset();
    assert(e06_inference_init("missing", "input.bin", "output.bin") == E06_ERR_IO);
}
static void test_reorder_logits_reference_and_timing(void) {
    e06_result_t result;
    const int16_t first[] = {0,768,1,769,2,770,3,771};
    fake_reset();
    assert(init_inference() == E06_OK);
    assert(e06_inference_input_data() != NULL);
    assert(e06_inference_input_bytes() == sizeof(fake.input));
    assert(memcmp(e06_inference_input_data(), fake.input, sizeof(fake.input)) == 0);
    assert(fake.starts == 0 && fake.transfers == 0 && fake.ticks == 0);
    assert(fake.weight_address != 0 && fake.layers == 12);
    assert(e06_inference_run(&result) == E06_OK);
    assert(memcmp(fake.transmitted, first, sizeof(first)) == 0);
    assert(fake.transmitted[1536] == 1536 && fake.transmitted[1537] == 2304);
    assert(fake.transmitted[65536] == -512); /* token/channel reorder plus int16 cast */
    assert(result.mismatch_count == 0 && result.predicted_class == 1);
    assert(result.total_ticks == 90 && result.pl_ticks == 50);
    assert(result.mm2s_ticks == 20 && result.s2mm_ticks == 50);
    assert(!fake.cache_order_error && fake.invalidate_output == 2 && !fake.metric_enabled);
    assert(strcmp(e06_inference_last_error(), "") == 0);
    fake.logits[999] = 42;
    assert(e06_inference_run(&result) == E06_ERR_MISMATCH);
    assert(result.mismatch_count == 1 && result.predicted_class == 1);
    assert(strlen(e06_inference_last_error()) > 0);
    fake.logits[999] = 0x7fff6;
    fake.logits[1] = (int32_t)0xfffbffffu; /* high bits must be discarded */
    assert(e06_inference_run(&result) == E06_OK);
    fake.logits[0] = 0x3ffff; /* first index wins an argmax tie */
    assert(e06_inference_run(&result) == E06_ERR_MISMATCH);
    assert(result.mismatch_count == 1 && result.predicted_class == 0);
}
static void test_dma_and_accelerator_failures(void) {
    e06_result_t result;
    for (int direction = 0; direction < 2; ++direction) {
        fake_reset(); assert(init_inference() == E06_OK);
        fake.dma_error_direction = direction;
        assert(e06_inference_run(&result) == E06_ERR_DMA);
        assert(!fake.metric_enabled && strlen(e06_inference_last_error()) > 0);
        assert(e06_inference_run(&result) == E06_ERR_INIT);
        fake_reset(); assert(init_inference() == E06_OK);
        fake.dma_busy_direction = direction;
        assert(e06_inference_run(&result) == E06_ERR_TIMEOUT);
        assert(!fake.metric_enabled);
    }
    fake_reset(); assert(init_inference() == E06_OK);
    fake.accelerator_stuck = 1;
    assert(e06_inference_run(&result) == E06_ERR_TIMEOUT);
    assert(result.predicted_class == -1 && !fake.metric_enabled);
    assert(e06_inference_run(&result) == E06_ERR_INIT);
}
static void test_telemetry_independent_validity(void) {
    e06_telemetry_t sample;
    fake_reset(); assert(e06_telemetry_init() == E06_OK);
    assert(e06_telemetry_sample(&sample) == E06_OK);
    /* 17 rails at 2 mW, VCCINT at 5 mW; 1 V bus and signed shunt code 4. */
    assert(sample.monitored_power_uW == 39000 && sample.temperature_mC == 42250);
    assert(sample.power_valid == 1 && sample.temperature_valid == 1);
    assert(sample.timestamp_ticks == 0);
    assert(strcmp(e06_telemetry_last_error(), "") == 0);
    fake.temperature_raw = 0;
    assert(e06_telemetry_sample(&sample) == E06_ERR_SENSOR);
    assert(sample.power_valid == 1 && sample.monitored_power_uW == 39000);
    assert(sample.temperature_valid == 0 && sample.temperature_mC == INT32_MIN);
    fake.temperature_raw = 30000; fake.fail_rail = 10;
    assert(e06_telemetry_sample(&sample) == E06_ERR_SENSOR);
    assert(sample.power_valid == 0 && sample.monitored_power_uW == INT64_MIN);
    assert(sample.temperature_valid == 1 && sample.temperature_mC == 42250);
    fake.temperature_C = NAN;
    assert(e06_telemetry_sample(&sample) == E06_ERR_SENSOR);
    assert(sample.power_valid == 0 && sample.temperature_valid == 0);
    assert(sample.temperature_mC == INT32_MIN && sample.monitored_power_uW == INT64_MIN);
    assert(strlen(e06_telemetry_last_error()) > 0);
    fake_reset(); fake.iic_error = 1;
    assert(e06_telemetry_init() == E06_ERR_SENSOR);
    assert(e06_telemetry_sample(&sample) == E06_ERR_SENSOR);
    assert(!sample.power_valid && sample.temperature_valid);
    fake_reset(); fake.sysmon_error = 1;
    assert(e06_telemetry_init() == E06_ERR_SENSOR);
    assert(e06_telemetry_sample(&sample) == E06_ERR_SENSOR);
    assert(sample.power_valid && !sample.temperature_valid);
    fake_reset(); fake.sysmon_error = fake.iic_error = 1;
    assert(e06_telemetry_init() == E06_ERR_SENSOR);
    assert(e06_telemetry_sample(&sample) == E06_ERR_SENSOR);
    assert(!sample.power_valid && !sample.temperature_valid);
    fake_reset(); fake.wrong_identity = 1;
    assert(e06_telemetry_init() == E06_ERR_SENSOR);
    assert(e06_telemetry_sample(&sample) == E06_ERR_SENSOR);
    assert(!sample.power_valid && sample.temperature_valid);
    fake_reset(); fake.bus_busy = 1;
    assert(e06_telemetry_init() == E06_ERR_SENSOR);
    fake_reset(); assert(e06_telemetry_init() == E06_OK);
    fake.temperature_C = 1000.0f;
    assert(e06_telemetry_sample(&sample) == E06_ERR_SENSOR);
    assert(sample.power_valid && !sample.temperature_valid);
}
int main(void) {
    fake_reset();
    test_arguments_and_uninitialized();
    test_loading_and_init_errors();
    test_reorder_logits_reference_and_timing();
    test_dma_and_accelerator_failures();
    test_telemetry_independent_validity();
    puts("E06 module tests passed");
    return 0;
}
