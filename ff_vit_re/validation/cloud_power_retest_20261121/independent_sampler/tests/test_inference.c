/* Regression of the copied, real DMA/input/output verification implementation. */
#include "e06_inference.h"
#include "fake_bsp/e06_fake_bsp.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static int init(void){return e06_inference_init("weights.bin","input.bin","output.bin");}
int main(void){
    e06_result_t result;
    for(unsigned f=0;f<3;f++){
        fake_reset();--fake.file_sizes[f];assert(init()==E06_ERR_IO);
        fake_reset();++fake.file_sizes[f];assert(init()==E06_ERR_IO);
    }
    fake_reset();assert(init()==E06_OK);
    assert(e06_inference_input_bytes()==602112&&memcmp(e06_inference_input_data(),fake.input,602112)==0);
    assert(e06_inference_run(&result)==E06_OK&&result.mismatch_count==0&&result.predicted_class==1);
    const int16_t expected[8]={0,768,1,769,2,770,3,771};
    assert(!memcmp(fake.transmitted,expected,sizeof(expected)));
    fake.logits[999]=42;assert(e06_inference_run(&result)==E06_ERR_MISMATCH&&result.mismatch_count==1);
    fake_reset();assert(!init());fake.dma_error_direction=1;
    assert(e06_inference_run(&result)==E06_ERR_DMA);assert(e06_inference_run(&result)==E06_ERR_INIT);
    fake_reset();assert(!init());fake.accelerator_stuck=1;
    assert(e06_inference_run(&result)==E06_ERR_TIMEOUT);
    puts("FIXED_INPUT_DMA_OUTPUT_VERIFICATION_OK");return 0;
}
