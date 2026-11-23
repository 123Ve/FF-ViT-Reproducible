#ifndef E06_INFERENCE_H
#define E06_INFERENCE_H
#include <stddef.h>
#include <stdint.h>
#include "e06_status.h"
typedef struct {
    uint32_t mismatch_count;
    int32_t predicted_class;
    uint64_t total_ticks;
    uint64_t pl_ticks;
    uint64_t mm2s_ticks;
    uint64_t s2mm_ticks;
} e06_result_t;
/* Single-owner API; init loads SD artifacts but executes no inference. */
int e06_inference_init(const char *weights_path, const char *input_path,
                       const char *reference_path);
/* DMA errors/timeouts invalidate initialization. Caller must quiesce/recover
 * hardware before reinitializing; this module does not reset the PL fabric. */
int e06_inference_run(e06_result_t *out);
/* Exact fixed E06 input bytes loaded during init, for the transport baseline. */
const void *e06_inference_input_data(void);
size_t e06_inference_input_bytes(void);
const char *e06_inference_last_error(void);
#endif
