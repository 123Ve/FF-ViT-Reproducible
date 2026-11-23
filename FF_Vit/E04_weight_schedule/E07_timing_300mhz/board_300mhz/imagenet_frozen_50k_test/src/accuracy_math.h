#ifndef E07_ACCURACY_MATH_H
#define E07_ACCURACY_MATH_H
#include <stdint.h>
#include <stddef.h>

static inline int32_t e07_decode_s19(uint32_t value) {
    value &= 0x7ffffu;
    return value >= 0x40000u ? (int32_t)value-524288 : (int32_t)value;
}

static inline void e07_top5(const int32_t logits[1000], uint32_t top[5]) {
    int32_t values[5]={-262145,-262145,-262145,-262145,-262145};
    for (unsigned k=0;k<5;k++) top[k]=1000;
    for (uint32_t c=0;c<1000;c++) {
        int32_t v=e07_decode_s19((uint32_t)logits[c]);
        for (unsigned k=0;k<5;k++) {
            if (v>values[k]) { /* stable ascending class ID on ties */
                for (unsigned j=4;j>k;j--) { values[j]=values[j-1]; top[j]=top[j-1]; }
                values[k]=v; top[k]=c; break;
            }
        }
    }
}

static inline uint32_t e07_crc32(const uint8_t *data, size_t length) {
    static uint32_t table[256];
    static int initialized=0;
    if (!initialized) {
        for (uint32_t i=0;i<256;i++) {
            uint32_t c=i;
            for (unsigned bit=0;bit<8;bit++) c=(c>>1)^((c&1u)?0xedb88320u:0u);
            table[i]=c;
        }
        initialized=1;
    }
    uint32_t crc=0xffffffffu;
    for (size_t i=0;i<length;i++) crc=table[(crc^data[i])&255u]^(crc>>8);
    return crc^0xffffffffu;
}

static inline int e07_valid_header(const uint32_t h[6]) {
    return h[0]==1 && h[1]>=1 && h[1]<=50000 && h[2]==301056 &&
           h[3]>=1 && h[3]<=1000 && h[4]==12 && h[5]==0;
}
#endif
