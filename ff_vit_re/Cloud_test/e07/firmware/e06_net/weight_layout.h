#ifndef E06_WEIGHT_LAYOUT_H
#define E06_WEIGHT_LAYOUT_H

#include <stdint.h>

#define E06_C 192
#define E06_T 196
#define E06_CI 768
#define E06_NUM_LAYERS 12
#define E06_NUM_CLASSES 1000
#define E06_BLOCK_WEIGHT_BYTES 231008u

typedef struct __attribute__((aligned(16))) { uint8_t bytes[16]; } Pack128_3_C;
typedef struct __attribute__((aligned(16))) { int16_t lane[8]; } Pack128_16_C;

typedef struct __attribute__((aligned(16))) {
    Pack128_3_C q_weight[1152];
    Pack128_3_C k_weight[1152];
    Pack128_3_C v_weight[1152];
    Pack128_16_C q_bias[24];
    Pack128_16_C k_bias[24];
    Pack128_16_C v_bias[24];
    Pack128_3_C o_weight[1152];
    Pack128_16_C o_bias[24];
    int32_t attn_scalars[3];
    int32_t ln_scalars[7];
    int32_t ln_lnw[E06_C];
    int64_t ln_lnb[E06_C];
    int32_t ln_rsqrt_table[128];
    int32_t qq_scalars[4];
    int8_t qq_table[64];
    int32_t kq_scalars[4];
    int8_t kq_table[64];
    int32_t vq_scalars[4];
    int8_t vq_table[64];
    int32_t aq_scalars[4];
    int8_t aq_table[64];
    int32_t softmax_scalars[14];
    uint16_t softmax_exp_table[32];
    uint8_t softmax_recip_table_one[64];
    int8_t softmax_recip_table_two[64];
} AttnLayerWeights_C;

typedef struct __attribute__((aligned(16))) {
    Pack128_3_C m1_weight[4608];
    Pack128_16_C m1_bias[96];
    Pack128_3_C m2_weight[4608];
    Pack128_16_C m2_bias[24];
    int32_t mlp_scalars[2];
    int32_t ln_scalars[7];
    int32_t ln_lnw[E06_C];
    int64_t ln_lnb[E06_C];
    int32_t ln_rsqrt_table[128];
    int32_t ge_scalars[4];
    uint8_t ge_table[64];
} MlpLayerWeights_C;

typedef struct __attribute__((aligned(16))) {
    AttnLayerWeights_C attn_weights;
    MlpLayerWeights_C mlp_weights;
} BlockLayerWeights_C;

_Static_assert(sizeof(AttnLayerWeights_C) == 78688u, "Attention weight layout mismatch");
_Static_assert(sizeof(MlpLayerWeights_C) == 152320u, "MLP weight layout mismatch");
_Static_assert(sizeof(BlockLayerWeights_C) == E06_BLOCK_WEIGHT_BYTES,
               "Block weight layout mismatch");

#endif
