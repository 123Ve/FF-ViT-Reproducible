#ifndef U3_ACCURACY_MATH_H
#define U3_ACCURACY_MATH_H
#include <stdint.h>
#include <stddef.h>
static inline int32_t e07_decode_s19(uint32_t v) {
    v &= 0x7ffffu;
    return v>=0x40000u ? (int32_t)v-524288 : (int32_t)v;
}
static inline void e07_top5(const int32_t logits[1000], unsigned classes, uint32_t top[5]) {
    int32_t values[5]={-262145,-262145,-262145,-262145,-262145};
    for(unsigned k=0;k<5;k++) top[k]=1000;
    for(uint32_t c=0;c<classes;c++) {
        int32_t v=e07_decode_s19((uint32_t)logits[c]);
        for(unsigned k=0;k<5;k++) if(v>values[k]) {
            for(unsigned j=4;j>k;j--) {values[j]=values[j-1];top[j]=top[j-1];}
            values[k]=v;top[k]=c;break;
        }
    }
}
static inline uint32_t e07_crc32(const uint8_t *data,size_t length) {
    static uint32_t table[256]; static int initialized=0;
    if(!initialized) {
        for(uint32_t i=0;i<256;i++) {
            uint32_t c=i;
            for(unsigned b=0;b<8;b++) c=(c>>1)^((c&1u)?0xedb88320u:0u);
            table[i]=c;
        }
        initialized=1;
    }
    uint32_t crc=0xffffffffu;
    for(size_t i=0;i<length;i++) crc=table[(crc^data[i])&255u]^(crc>>8);
    return crc^0xffffffffu;
}
static inline int e07_valid_header(const uint32_t h[8],uint32_t count,uint32_t classes,uint32_t crc) {
    return h[0]==1 && h[1]==count && h[2]==301056 && h[3]==1000 &&
           h[4]==12 && h[5]==classes && h[6]==crc && h[7]==1000;
}
#endif
