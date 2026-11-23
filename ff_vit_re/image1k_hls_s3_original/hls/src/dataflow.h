#ifndef __DATAFLOW__
#define __DATAFLOW__
#include "common.h"
#include <stdint.h>
#include <ap_int.h>

const int C = 192;
const int MLP_CH = 768;
const int T = 196;


struct alignas(16) Pack128_8 {

    ap_uint<128> d;
    int8_t get(int idx) const {
        #pragma HLS inline
        return (ap_int<8>)d.range(idx*8+7, idx*8);
    }

};

struct alignas(16) Pack128_16 {
    ap_uint<128> d;
    int16_t get(int idx) const {
        #pragma HLS inline
        return (ap_int<16>)d.range(idx*16+15, idx*16);
    }

};
// 🚀 新增：128-bit 容纳 42 个 3-bit 权重的超级结构体
struct alignas(16) Pack128_3 {
    ap_uint<128> d;
    
    int8_t get(int idx) const {
        #pragma HLS inline
        // 自动处理 3-bit 补码符号扩展
        ap_int<3> val = d.range(idx * 3 + 2, idx * 3);
        return (int8_t)val; 
    }
};

struct AttnLayerWeights {

    // Pack128_8  q_weight[2304];
    // Pack128_8  k_weight[2304];
    // Pack128_8  v_weight[2304];
    Pack128_3  q_weight[1152];
    Pack128_3  k_weight[1152];
    Pack128_3  v_weight[1152];

    Pack128_16 q_bias[24];
    Pack128_16 k_bias[24];
    Pack128_16 v_bias[24];
    //Pack128_8  o_weight[2304];
    Pack128_3  o_weight[1152];
    Pack128_16 o_bias[24];

    int32_t  attn_scalars[3];
    int32_t  ln_scalars[7];
    int32_t  ln_lnw[C];
    int64_t  ln_lnb[C];
    int32_t  ln_rsqrt_table[128];
    int32_t  qq_scalars[4];
    int8_t   qq_table[64];
    int32_t  kq_scalars[4];
    int8_t   kq_table[64];
    int32_t  vq_scalars[4];
    int8_t   vq_table[64];
    int32_t  aq_scalars[4];
    int8_t   aq_table[64];
    int32_t  softmax_scalars[14];
    uint16_t softmax_exp_table[32];
    uint8_t  softmax_recip_table_one[64];
    int8_t   softmax_recip_table_two[64];
};

// // 2. MLP 权重
// struct MlpLayerWeights {
//     // 147456 / 16 = 9216
//     Pack128_8  m1_weight[9216];
//     // 768 / 8 = 96
//     Pack128_16 m1_bias[96];
//     Pack128_8  m2_weight[9216];
//     // 192 / 8 = 24
//     Pack128_16 m2_bias[24];

//     int32_t  mlp_scalars[2];
//     int32_t  ln_scalars[7];
//     int32_t  ln_lnw[C];
//     int64_t  ln_lnb[C];
//     int32_t  ln_rsqrt_table[128];
//     int32_t  ge_scalars[4];
//     uint8_t  ge_table[64];
// };
// 2. MLP 权重 (引入 3-bit 极致打包)
struct MlpLayerWeights {
    // 147456 / 42 = 3510.85 -> 向上取整为 4608
    Pack128_3  m1_weight[4608];
    
    // Bias 依然是 16-bit
    // 768 / 8 = 96
    Pack128_16 m1_bias[96];
    
    // 147456 / 42 = 4608
    Pack128_3  m2_weight[4608];
    
    // 192 / 8 = 24
    Pack128_16 m2_bias[24];

    int32_t  mlp_scalars[2];
    int32_t  ln_scalars[7];
    int32_t  ln_lnw[C];
    int64_t  ln_lnb[C];
    int32_t  ln_rsqrt_table[128];
    int32_t  ge_scalars[4];
    uint8_t  ge_table[64];
};

struct BlockLayerWeights {
    AttnLayerWeights attn_weights;
    MlpLayerWeights  mlp_weights;
};


const int CI = 768;

struct PatchEmbedWeights {
    int32_t scalars[4];
    int32_t weight[C * CI];
    int32_t bias[T * C];
    int32_t cls[C];
};

struct HeadWeights {
    int32_t  ln_scalars[8];
    int32_t  ln_lnw[C];
    int64_t  ln_lnb[C];
    int32_t  ln_rsqrt_table[128];
    int8_t   weight[1000 * C];
    int32_t  bias[1000];
};

#endif
