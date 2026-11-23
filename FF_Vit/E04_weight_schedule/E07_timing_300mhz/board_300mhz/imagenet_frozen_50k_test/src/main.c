/* PS-only multi-image evaluation of the unchanged E07 bitstream and weights. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "ff.h"
#include "xaxidma.h"
#include "xil_cache.h"
#include "xil_printf.h"
#include "xparameters.h"
#include "xstatus.h"
#include "xiltimer.h"
#include "xvit_block_top.h"
#include "weight_layout.h"
#include "accuracy_math.h"

#define FRAME_BYTES 301056u
#define WEIGHTS_CRC 0x7ec991e5u
#define MAX_FRAME_SECONDS 2u
static BlockLayerWeights_C weights[E07_NUM_LAYERS] __attribute__((aligned(64)));
static int32_t raw_input[E07_T*E07_CI] __attribute__((aligned(64)));
static int16_t dma_input[E07_T*E07_CI] __attribute__((aligned(64)));
static int32_t dma_output[E07_NUM_CLASSES] __attribute__((aligned(64)));
static int32_t reference_output[E07_NUM_CLASSES] __attribute__((aligned(64)));
static FATFS fatfs;
static XAxiDma dma;
static XVit_block_top accelerator;

static int read_exact(FIL *f, void *data, UINT bytes) {
    UINT total=0;
    while (total<bytes) {
        UINT got=0;
        if (f_read(f,(uint8_t *)data+total,bytes-total,&got)!=FR_OK || got==0)
            return XST_FAILURE;
        total+=got;
    }
    return XST_SUCCESS;
}

static int load_file(const char *name, void *data, UINT bytes) {
    FIL f;
    if (f_open(&f,name,FA_READ)!=FR_OK) return XST_FAILURE;
    int result=f_size(&f)==bytes ? read_exact(&f,data,bytes) : XST_FAILURE;
    if (f_close(&f)!=FR_OK) result=XST_FAILURE;
    return result;
}

static int write_exact(FIL *f, const void *data, UINT bytes) {
    UINT got=0;
    return f_write(f,data,bytes,&got)==FR_OK && got==bytes ? XST_SUCCESS : XST_FAILURE;
}

static int initialize_hardware(void) {
    XAxiDma_Config *dc=XAxiDma_LookupConfig(XPAR_XAXIDMA_0_BASEADDR);
    XVit_block_top_Config *ac=XVit_block_top_LookupConfig(XPAR_XVIT_BLOCK_TOP_0_BASEADDR);
    if (!dc || !ac || XAxiDma_CfgInitialize(&dma,dc)!=XST_SUCCESS || XAxiDma_HasSg(&dma))
        return XST_FAILURE;
    XAxiDma_IntrDisable(&dma,XAXIDMA_IRQ_ALL_MASK,XAXIDMA_DMA_TO_DEVICE);
    XAxiDma_IntrDisable(&dma,XAXIDMA_IRQ_ALL_MASK,XAXIDMA_DEVICE_TO_DMA);
    return XVit_block_top_CfgInitialize(&accelerator,ac);
}

static int run_one_frame(void) {
    XTime start,now;
    XTime_GetTime(&start);
    Xil_DCacheFlushRange((INTPTR)dma_input,sizeof(dma_input));
    Xil_DCacheInvalidateRange((INTPTR)dma_output,sizeof(dma_output));
    if (XAxiDma_SimpleTransfer(&dma,(UINTPTR)dma_output,sizeof(dma_output),
                              XAXIDMA_DEVICE_TO_DMA)!=XST_SUCCESS) return XST_FAILURE;
    XVit_block_top_Start(&accelerator);
    if (XAxiDma_SimpleTransfer(&dma,(UINTPTR)dma_input,sizeof(dma_input),
                              XAXIDMA_DMA_TO_DEVICE)!=XST_SUCCESS) return XST_FAILURE;
    while (XAxiDma_Busy(&dma,XAXIDMA_DMA_TO_DEVICE) ||
           XAxiDma_Busy(&dma,XAXIDMA_DEVICE_TO_DMA) || !XVit_block_top_IsDone(&accelerator)) {
        uint32_t tx=XAxiDma_ReadReg(dma.RegBase,XAXIDMA_TX_OFFSET+XAXIDMA_SR_OFFSET);
        uint32_t rx=XAxiDma_ReadReg(dma.RegBase,XAXIDMA_RX_OFFSET+XAXIDMA_SR_OFFSET);
        if ((tx|rx)&XAXIDMA_ERR_ALL_MASK) {
            xil_printf("DMA_ERROR TX=%08lx RX=%08lx\r\n",(unsigned long)tx,(unsigned long)rx);
            return XST_FAILURE;
        }
        XTime_GetTime(&now);
        if ((uint64_t)(now-start)>(uint64_t)COUNTS_PER_SECOND*MAX_FRAME_SECONDS) {
            xil_printf("FRAME_TIMEOUT\r\n");
            return XST_FAILURE;
        }
    }
    Xil_DCacheInvalidateRange((INTPTR)dma_output,sizeof(dma_output));
    return XST_SUCCESS;
}

static int baseline_check(void) {
    if (load_file("input.bin",raw_input,sizeof(raw_input))!=XST_SUCCESS ||
        load_file("output.bin",reference_output,sizeof(reference_output))!=XST_SUCCESS)
        return XST_FAILURE;
    if (e07_crc32((const uint8_t *)raw_input,sizeof(raw_input))!=0x50a9dfe9u ||
        e07_crc32((const uint8_t *)reference_output,sizeof(reference_output))!=0x58b77848u)
        return XST_FAILURE;
    unsigned pos=0;
    for (int tt=0;tt<E07_T/2;tt++)
        for (int c=0;c<E07_CI;c++)
            for (int tp=0;tp<2;tp++)
                dma_input[pos++]=(int16_t)raw_input[(tt*2+tp)*E07_CI+c];
    if (run_one_frame()!=XST_SUCCESS || run_one_frame()!=XST_SUCCESS) return XST_FAILURE;
    unsigned mismatch=0;
    for (int c=0;c<1000;c++)
        if (e07_decode_s19((uint32_t)dma_output[c])!=reference_output[c]) mismatch++;
    xil_printf("BASELINE_BIT_EXACT_MISMATCHES=%u\r\n",mismatch);
    return mismatch==0 ? XST_SUCCESS : XST_FAILURE;
}

static int evaluate(void) {
    FIL index,chunk,result,logits;
    int index_open=0,chunk_open=0,result_open=0,logits_open=0;
    const char *stage="INDEX_OPEN";
    uint32_t done=0,correct1=0,correct5=0;
    uint32_t h[6],record[3];
    uint64_t total_infer=0,total_read=0,total_log=0;
    XTime wall_start=0,wall_end=0;
    uint8_t magic[8];
    if (f_open(&index,"INDEX.BIN",FA_READ)!=FR_OK) goto fail;
    index_open=1;
    stage="INDEX_HEADER";
    if (read_exact(&index,magic,8)!=XST_SUCCESS || memcmp(magic,"IM1KE07\0",8)!=0 ||
        read_exact(&index,h,sizeof(h))!=XST_SUCCESS || !e07_valid_header(h) ||
        f_size(&index)!=(FSIZE_t)(32u+12u*h[1])) goto fail;
    xil_printf("DATASET_FRAMES=%lu CHUNK_FRAMES=%lu\r\n",(unsigned long)h[1],(unsigned long)h[3]);
    stage="LOG_OPEN";
    /* Refuse to overwrite previous board results. Rename/remove on the SD
       card intentionally before another run; source/deployment remains safe. */
    if (f_open(&result,"RESULT.CSV",FA_WRITE|FA_CREATE_NEW)!=FR_OK) goto fail;
    result_open=1;
    if (f_open(&logits,"LOGITS.BIN",FA_WRITE|FA_CREATE_NEW)!=FR_OK) goto fail;
    logits_open=1;
    const char *csv="index,label,pred1,pred2,pred3,pred4,pred5,correct1,correct5,inference_ticks,input_crc32\r\n";
    if (write_exact(&result,csv,(UINT)strlen(csv))!=XST_SUCCESS) goto fail;
    XTime_GetTime(&wall_start);
    for (uint32_t i=0;i<h[1];i++) {
        XTime a,b;
        stage="INDEX_RECORD";
        if (read_exact(&index,record,sizeof(record))!=XST_SUCCESS || record[0]!=i || record[1]>=1000)
            goto fail;
        if (i%h[3]==0) {
            if (chunk_open) { if (f_close(&chunk)!=FR_OK) goto fail; chunk_open=0; }
            char filename[16];
            snprintf(filename,sizeof(filename),"I%03lu.BIN",(unsigned long)(i/h[3]));
            stage="CHUNK_OPEN";
            if (f_open(&chunk,filename,FA_READ)!=FR_OK) goto fail;
            chunk_open=1;
            uint32_t remaining=h[1]-i;
            uint32_t n=remaining<h[3] ? remaining : h[3];
            if (f_size(&chunk)!=(FSIZE_t)n*FRAME_BYTES) goto fail;
        }
        stage="INPUT_READ";
        XTime_GetTime(&a);
        if (read_exact(&chunk,dma_input,sizeof(dma_input))!=XST_SUCCESS) goto fail;
        XTime_GetTime(&b); total_read+=(uint64_t)(b-a);
        stage="INPUT_CRC";
        if (e07_crc32((const uint8_t *)dma_input,sizeof(dma_input))!=record[2]) goto fail;
        stage="INFERENCE";
        XTime_GetTime(&a);
        if (run_one_frame()!=XST_SUCCESS) goto fail;
        XTime_GetTime(&b);
        uint64_t ticks=(uint64_t)(b-a);
        total_infer+=ticks;
        uint32_t top[5];
        e07_top5(dma_output,top);
        unsigned hit1=top[0]==record[1],hit5=0;
        for (unsigned k=0;k<5;k++) if (top[k]==record[1]) hit5=1;
        char line[192];
        int n=snprintf(line,sizeof(line),"%lu,%lu,%lu,%lu,%lu,%lu,%lu,%u,%u,%llu,%08lx\r\n",
            (unsigned long)i,(unsigned long)record[1],(unsigned long)top[0],(unsigned long)top[1],
            (unsigned long)top[2],(unsigned long)top[3],(unsigned long)top[4],hit1,hit5,
            (unsigned long long)ticks,(unsigned long)record[2]);
        stage="LOG_WRITE";
        if (n<=0 || (size_t)n>=sizeof(line)) goto fail;
        for (int c=0;c<1000;c++) dma_output[c]=e07_decode_s19((uint32_t)dma_output[c]);
        XTime_GetTime(&a);
        if (write_exact(&result,line,(UINT)n)!=XST_SUCCESS ||
            write_exact(&logits,dma_output,sizeof(dma_output))!=XST_SUCCESS) goto fail;
        if ((i+1)%100==0 && (f_sync(&result)!=FR_OK || f_sync(&logits)!=FR_OK)) goto fail;
        XTime_GetTime(&b); total_log+=(uint64_t)(b-a);
        correct1+=hit1; correct5+=hit5; done++;
        if (done%100==0 || done==h[1])
            xil_printf("PROGRESS=%lu/%lu TOP1_CORRECT=%lu TOP5_CORRECT=%lu\r\n",
                (unsigned long)done,(unsigned long)h[1],(unsigned long)correct1,(unsigned long)correct5);
    }
    stage="FINAL_SYNC";
    if (f_sync(&result)!=FR_OK || f_sync(&logits)!=FR_OK) goto fail;
    XTime_GetTime(&wall_end);
    {
        char summary[1024];
        uint32_t top1_ppm=(uint32_t)((uint64_t)correct1*1000000/done);
        uint32_t top5_ppm=(uint32_t)((uint64_t)correct5*1000000/done);
        int n=snprintf(summary,sizeof(summary),
            "MODEL=FROZEN_E07_UNCHANGED\r\nBOARD_EVALUATION_COMPLETE=YES\r\n"
            "REQUESTED_FRAMES=%lu\r\nCOMPLETED_FRAMES=%lu\r\nFAILED_FRAMES=0\r\n"
            "TOP1_CORRECT=%lu\r\nTOP5_CORRECT=%lu\r\nTOP1_PPM=%lu\r\nTOP5_PPM=%lu\r\n"
            "TIMER_HZ=%lu\r\nINFERENCE_TICKS=%llu\r\nDATASET_WALL_TICKS=%llu\r\n"
            "SD_INPUT_READ_TICKS=%llu\r\nRESULT_LOG_TICKS=%llu\r\n"
            "INFERENCE_INCLUDES=PS_CACHE_DMA_PL_COMPLETION\r\n"
            "INFERENCE_EXCLUDES=SD_READ_CRC_ARGMAX_LOG_UART\r\n"
            "DATASET_WALL_INCLUDES=SD_CRC_INFERENCE_ARGMAX_LOG_PROGRESS_UART\r\n",
            (unsigned long)h[1],(unsigned long)done,(unsigned long)correct1,(unsigned long)correct5,
            (unsigned long)top1_ppm,(unsigned long)top5_ppm,(unsigned long)COUNTS_PER_SECOND,
            (unsigned long long)total_infer,(unsigned long long)(wall_end-wall_start),
            (unsigned long long)total_read,(unsigned long long)total_log);
        FIL sum;
        if (n<=0 || (size_t)n>=sizeof(summary) ||
            f_open(&sum,"ACCSUM.TXT",FA_WRITE|FA_CREATE_NEW)!=FR_OK) goto fail;
        int ok=write_exact(&sum,summary,(UINT)n);
        if (f_close(&sum)!=FR_OK || ok!=XST_SUCCESS) goto fail;
        xil_printf("TOP1=%lu.%04lu%% TOP5=%lu.%04lu%%\r\n",
            (unsigned long)(top1_ppm/10000),(unsigned long)(top1_ppm%10000),
            (unsigned long)(top5_ppm/10000),(unsigned long)(top5_ppm%10000));
        xil_printf("COMPLETED_FRAMES=%lu INFERENCE_TICKS=%llu DATASET_WALL_TICKS=%llu\r\n",
            (unsigned long)done,(unsigned long long)total_infer,(unsigned long long)(wall_end-wall_start));
    }
    {
        int close_ok=1;
        if (chunk_open && f_close(&chunk)!=FR_OK) close_ok=0;
        if (f_close(&index)!=FR_OK || f_close(&result)!=FR_OK || f_close(&logits)!=FR_OK) close_ok=0;
        if (!close_ok) { xil_printf("CLOSE_FAIL\r\n"); return XST_FAILURE; }
    }
    xil_printf("ACCURACY_RUN_COMPLETE files=RESULT.CSV,LOGITS.BIN,ACCSUM.TXT\r\n");
    return XST_SUCCESS;
fail:
    xil_printf("ACCURACY_RUN_FAIL stage=%s completed=%lu (partial results are not full accuracy)\r\n",
        stage,(unsigned long)done);
    if (chunk_open) f_close(&chunk);
    if (index_open) f_close(&index);
    if (result_open) f_close(&result);
    if (logits_open) f_close(&logits);
    return XST_FAILURE;
}

int main(void) {
    xil_printf("\r\nE07 frozen-model ImageNet real-image accuracy test\r\n");
    xil_printf("PL_UNCHANGED=YES WEIGHTS_UNCHANGED=YES FRAME_OVERLAP=NO\r\n");
    xil_printf("MODEL_SCOPE=CURRENT_E07_NOT_OTHER_IMAGENET_QAT_MODEL\r\n");
    xil_printf("PL_MHZ=300.215099 TIMER_HZ=%lu\r\n",(unsigned long)COUNTS_PER_SECOND);
    if (initialize_hardware()!=XST_SUCCESS || f_mount(&fatfs,"0:/",1)!=FR_OK) {
        xil_printf("INIT_FAIL\r\n"); return XST_FAILURE;
    }
    if (load_file("weights.bin",weights,sizeof(weights))!=XST_SUCCESS ||
        e07_crc32((const uint8_t *)weights,sizeof(weights))!=WEIGHTS_CRC) {
        xil_printf("FROZEN_WEIGHTS_IDENTITY_FAIL\r\n"); return XST_FAILURE;
    }
    Xil_DCacheFlushRange((INTPTR)weights,sizeof(weights));
    XVit_block_top_Set_ext_weights(&accelerator,(u64)(UINTPTR)weights);
    XVit_block_top_Set_num_layers(&accelerator,E07_NUM_LAYERS);
    if (baseline_check()!=XST_SUCCESS) { xil_printf("BASELINE_FAIL\r\n"); return XST_FAILURE; }
    return evaluate();
}
