#ifndef __INT_ATTN_H__
#define __INT_ATTN_H__

#include "common.h"
#include "layernorm.h"
#include "matmul.h"
#include "quant.h"
#include "head_split.h"
#include "fused_flash_attn.h" 
#include "dataflow.h"
using namespace std;

template<
    // attn global shapes
    int     H,                  // head number
    int     T,                  // input  feature map sequence length, shared by all layers
    int     TP,                 // input  feature map sequence parallel degree
    int     C,                  // input & output feature map channels
    int     CAP,                // input & output feature map channel adaptive parallel degree, also for output
    int     RESI_CP,            // residual parallel degree

    // qkv generation parallel degree,
    int     MATMUL_QKV_CIP,   
    int     MATMUL_QKV_COP,  

    // qkv quantize parallel degree,
    int     Q_QKV_CP,

    // QK = R (保留接口)
    int     MATMUL_R_CIP,      
    int     MATMUL_R_COP,     

    // softmaxq for R (保留接口)
    int     RQ_CP,        

    // RV = A (保留接口)
    int     MATMUL_A_CIP,      
    int     MATMUL_A_COP,     

    // a quantize parallel degree
    int     AQ_CP,          

    // O
    int     MATMUL_O_CIP, 
    int     MATMUL_O_COP,       

    // attn global types
    class   __attn_if_t,        // input feature map type
    class   __attn_lnq_t,       // layernorm type
    class   __attn_q_t,         // query type
    class   __attn_k_t,         // key   type
    class   __attn_v_t,         // value type
    class   __attn_r_t,         // relation type
    class   __attn_a_t,         // attention type
    class   __attn_o_t,         // output feature map type
    class   __attn_qq_t,        // quantized query type
    class   __attn_kq_t,        // quantized key   type
    class   __attn_vq_t,        // quantized value type
    class   __attn_rq_t,        // quantized relation type
    class   __attn_aq_t,        // quantized attention type
    class   __attn_of_t,        // output feature map type

    // layernorm
    class   __ln_sum_t,         // sum type
    class   __ln_divc_t,        // type of sum(x) * C_1_m
    class   __ln_mu_t,          // type of x mean
    class   __ln_var_t,         // type of pow diff sum
    class   __ln_cursor_t,      // (varx + b) >> s1
    class   __ln_rsqrt_t,       // lookup table data
    class   __ln_affine_t,      // (x-mu) * rsqrt_table * lnw + lnb
    class   __ln_shift_t,       // >> s2
    int     LN_ENTRIES_RSQRT,

    // q generation
    class   __q_we_t,           // weight type
    class   __q_bi_t,
    int     Q_ADPT_FIFO_DEPTH,  
    int     Q_WIND_FIFO_DEPTH,  
    int     Q_WGHT_FIFO_DEPTH,  
    int     Q_MACS_FIFO_DEPTH,  
    int     Q_WEIGHT_RAM_STYLE, 
    bool    Q_USE_DSP,          

    // k generation
    class   __k_we_t,           
    class   __k_bi_t,
    int     K_ADPT_FIFO_DEPTH,  
    int     K_WIND_FIFO_DEPTH,  
    int     K_WGHT_FIFO_DEPTH,  
    int     K_MACS_FIFO_DEPTH,  
    int     K_WEIGHT_RAM_STYLE, 
    bool    K_USE_DSP,          

    // v generation
    class   __v_we_t,           
    class   __v_bi_t,
    int     V_ADPT_FIFO_DEPTH,  
    int     V_WIND_FIFO_DEPTH,  
    int     V_WGHT_FIFO_DEPTH,  
    int     V_MACS_FIFO_DEPTH,  
    int     V_WEIGHT_RAM_STYLE, 
    bool    V_USE_DSP,          

    // qq
    class   __qq_cursor_t,      
    int     QQ_ENTRIES,

    // kq
    class   __kq_cursor_t,      
    int     KQ_ENTRIES,

    // vq
    class   __vq_cursor_t,      
    int     VQ_ENTRIES,

    // aq
    class   __aq_cursor_t,      
    int     AQ_ENTRIES,

    // qk matmul (保留接口)
    int     QK_MATMUL_ADPT_FIFO_DEPTH,
    int     QK_MATMUL_WIND_FIFO_DEPTH,
    int     QK_MATMUL_WGHT_FIFO_DEPTH,
    int     QK_MATMUL_MACS_FIFO_DEPTH,
    int     QK_MATMUL_WEIGHT_RAM_STYLE,
    bool    QK_MATMUL_USE_DSP,

    // softmax
    class   __softmax_minus_t,  
    class   __softmax_cursor1_t,
    class   __softmax_exp_t,
    class   __softmax_acc_t,
    class   __softmax_recip_t,
    class   __softmax_cursor2_one_t,
    class   __softmax_cursor2_two_t,
    class   __softmax_affine_t,
    class   __softmax_cursor3_t,
    int     SOFTMAX_ENTRIES_EXP,
    int     SOFTMAX_ENTRIES_RECIP,

    // rv matmul (保留接口)
    int     RV_MATMUL_ADPT_FIFO_DEPTH,
    int     RV_MATMUL_WIND_FIFO_DEPTH,
    int     RV_MATMUL_WGHT_FIFO_DEPTH,
    int     RV_MATMUL_MACS_FIFO_DEPTH,
    int     RV_MATMUL_WEIGHT_RAM_STYLE,
    bool    RV_MATMUL_USE_DSP,

    // o matmul
    class   __o_we_t,           
    class   __o_bi_t,
    int     O_MATMUL_ADPT_FIFO_DEPTH,
    int     O_MATMUL_WIND_FIFO_DEPTH,
    int     O_MATMUL_WGHT_FIFO_DEPTH,
    int     O_MATMUL_MACS_FIFO_DEPTH,
    int     O_MATMUL_WEIGHT_RAM_STYLE,
    bool    O_MATMUL_USE_DSP,

    // FIFO depths
    int     MAIN_FIFO_DEPTH,
    int     RESI_I_FIFO_DEPTH,
    int     RESI_FIFO_DEPTH,
    int     RESI_O_FIFO_DEPTH,
    int     LNQ_FIFO_DEPTH,
    int     LNQ_CP_FIFO_DEPTH,
    int     Q_FIFO_DEPTH,
    int     K_FIFO_DEPTH,
    int     V_FIFO_DEPTH,
    int     QQ_FIFO_DEPTH,
    int     KQ_FIFO_DEPTH,
    int     VQ_FIFO_DEPTH,
    int     QQ_HEAD_FIFO_DEPTH,
    int     KQ_HEAD_FIFO_DEPTH,
    int     VQ_HEAD_FIFO_DEPTH,
    int     R_HEAD_FIFO_DEPTH,
    int     RQ_HEAD_FIFO_DEPTH,
    int     KQ_RESHAPE_HEAD_FIFO_DEPTH,
    int     VQ_TRANSPOSE_HEAD_FIFO_DEPTH,
    int     A_HEAD_FIFO_DEPTH,
    int     A_FIFO_DEPTH,
    int     AQ_FIFO_DEPTH,
    int     O_FIFO_DEPTH
> class Attn{
public:

    static_assert(  C   % H     == 0, "C must be multiple of H"  );
    static_assert(  C   % CAP   == 0, "C must be multiple of CAP");
    static_assert(  T   % TP    == 0, "T must be multiple of TP" );

    static constexpr int CH  = C / H;
    static constexpr int TT  = T / TP;
    static constexpr int CAT = C / CAP;

    int RM, RS, RB;

    Layernorm   <__attn_if_t, __ln_sum_t, __ln_divc_t, __ln_mu_t, __ln_var_t, __ln_cursor_t, __ln_rsqrt_t, __ln_affine_t, __ln_shift_t, __attn_lnq_t, LN_ENTRIES_RSQRT, T, TP, C, CAP> lnq;

    Matmul      <__attn_lnq_t, __q_we_t,    __q_bi_t, __attn_q_t, T, TP, C,  MATMUL_QKV_CIP, CAP,      C,    MATMUL_QKV_COP,  Q_QKV_CP,     Q_ADPT_FIFO_DEPTH,  Q_WIND_FIFO_DEPTH,  Q_WGHT_FIFO_DEPTH,  Q_MACS_FIFO_DEPTH,  Q_WEIGHT_RAM_STYLE,  Q_USE_DSP >  matmul_gen_q;
    Matmul      <__attn_lnq_t, __k_we_t,    __k_bi_t, __attn_k_t, T, TP, C,  MATMUL_QKV_CIP, CAP,      C,    MATMUL_QKV_COP,  Q_QKV_CP,     K_ADPT_FIFO_DEPTH,  K_WIND_FIFO_DEPTH,  K_WGHT_FIFO_DEPTH,  K_MACS_FIFO_DEPTH,  K_WEIGHT_RAM_STYLE,  K_USE_DSP >  matmul_gen_k;
    Matmul      <__attn_lnq_t, __v_we_t,    __v_bi_t, __attn_v_t, T, TP, C,  MATMUL_QKV_CIP, CAP,      C,    MATMUL_QKV_COP,  Q_QKV_CP,     V_ADPT_FIFO_DEPTH,  V_WIND_FIFO_DEPTH,  V_WGHT_FIFO_DEPTH,  V_MACS_FIFO_DEPTH,  V_WEIGHT_RAM_STYLE,  V_USE_DSP >  matmul_gen_v;

    // ==========================================
    // 🚀 明确物理实例化 3 个独立的计算核心
    // ==========================================
    FlashAttentionHead<
        T, TP, CH, Q_QKV_CP, AQ_CP,
        __attn_qq_t, __attn_kq_t, __attn_vq_t, __attn_a_t,
        __softmax_minus_t, __softmax_cursor1_t, __softmax_exp_t, 
        __softmax_acc_t, __softmax_recip_t, __softmax_cursor2_one_t, 
        __softmax_cursor2_two_t, __softmax_affine_t, __softmax_cursor3_t,
        SOFTMAX_ENTRIES_EXP, SOFTMAX_ENTRIES_RECIP
    > flash_attn_engine_0;

    FlashAttentionHead<
        T, TP, CH, Q_QKV_CP, AQ_CP,
        __attn_qq_t, __attn_kq_t, __attn_vq_t, __attn_a_t,
        __softmax_minus_t, __softmax_cursor1_t, __softmax_exp_t, 
        __softmax_acc_t, __softmax_recip_t, __softmax_cursor2_one_t, 
        __softmax_cursor2_two_t, __softmax_affine_t, __softmax_cursor3_t,
        SOFTMAX_ENTRIES_EXP, SOFTMAX_ENTRIES_RECIP
    > flash_attn_engine_1;

    FlashAttentionHead<
        T, TP, CH, Q_QKV_CP, AQ_CP,
        __attn_qq_t, __attn_kq_t, __attn_vq_t, __attn_a_t,
        __softmax_minus_t, __softmax_cursor1_t, __softmax_exp_t, 
        __softmax_acc_t, __softmax_recip_t, __softmax_cursor2_one_t, 
        __softmax_cursor2_two_t, __softmax_affine_t, __softmax_cursor3_t,
        SOFTMAX_ENTRIES_EXP, SOFTMAX_ENTRIES_RECIP
    > flash_attn_engine_2;

    Matmul      <__attn_aq_t,  __o_we_t,    __o_bi_t, __attn_o_t, T, TP, C,  MATMUL_O_CIP,   AQ_CP,    C,    MATMUL_O_COP,    CAP,          O_MATMUL_ADPT_FIFO_DEPTH,  O_MATMUL_WIND_FIFO_DEPTH,  O_MATMUL_WGHT_FIFO_DEPTH,  O_MATMUL_MACS_FIFO_DEPTH,  O_MATMUL_WEIGHT_RAM_STYLE,  O_MATMUL_USE_DSP>  matmul_gen_o;

    Quant       <__attn_q_t, __qq_cursor_t, __attn_qq_t, T, TP, C, Q_QKV_CP, QQ_ENTRIES>    quant_q;
    Quant       <__attn_k_t, __kq_cursor_t, __attn_kq_t, T, TP, C, Q_QKV_CP, KQ_ENTRIES>    quant_k;
    Quant       <__attn_v_t, __vq_cursor_t, __attn_vq_t, T, TP, C, Q_QKV_CP, VQ_ENTRIES>    quant_v;
    Quant       <__attn_a_t, __aq_cursor_t, __attn_aq_t, T, TP, C, AQ_CP,    AQ_ENTRIES>    quant_a;

    HeadSplit   <__attn_qq_t, H, T, TP, C, Q_QKV_CP> split_q;
    HeadSplit   <__attn_kq_t, H, T, TP, C, Q_QKV_CP> split_k;
    HeadSplit   <__attn_vq_t, H, T, TP, C, Q_QKV_CP> split_v;
    HeadSplit   <__attn_a_t, H, T, TP, C, AQ_CP> merge_a;

    explicit Attn() :
        lnq                 ( ),
        matmul_gen_q        ( ),
        matmul_gen_k        ( ),
        matmul_gen_v        ( ),
        flash_attn_engine_0 ( ),
        flash_attn_engine_1 ( ),
        flash_attn_engine_2 ( ),
        quant_q             ( ),
        quant_k             ( ),
        quant_v             ( ),
        quant_a             ( ),
        matmul_gen_o        ( )
    {
    }

    void load_weights_from_bram(const AttnLayerWeights* local_weights) {
        #pragma HLS inline

        this->RM = local_weights->attn_scalars[0];
        this->RS = local_weights->attn_scalars[1];
        this->RB = (this->RS > 0) ? (1 << (this->RS - 1)) : 0;

        for (int i = 0; i < 7; i++) {
            #pragma HLS pipeline II=1
            this->lnq.local_scalars[i] = local_weights->ln_scalars[i];
        }

        int i_b = 0;
        for (int w = 0; w < C / 8; w++) {
            Pack128_16 p_q = local_weights->q_bias[w];
            Pack128_16 p_k = local_weights->k_bias[w];
            Pack128_16 p_v = local_weights->v_bias[w];
            Pack128_16 p_o = local_weights->o_bias[w];

            for (int b = 0; b < 8; b++) {
                #pragma HLS pipeline II=1
                this->matmul_gen_q.local_bias_ram[i_b] = p_q.get(b);
                this->matmul_gen_k.local_bias_ram[i_b] = p_k.get(b);
                this->matmul_gen_v.local_bias_ram[i_b] = p_v.get(b);
                this->matmul_gen_o.local_bias_ram[i_b] = p_o.get(b);

                this->lnq.local_lnw_ram[i_b]           = local_weights->ln_lnw[i_b];
                this->lnq.local_lnb_ram[i_b]           = local_weights->ln_lnb[i_b];
                i_b++;
            }
        }

        // int i_qkv = 0, j_qkv = 0;
        // for (int flat = 0; flat < C * C; flat++) {
        //     #pragma HLS pipeline II=1
        //     int w = flat >> 4;
        //     int b = flat & 15;

        //     Pack128_8 p_q = local_weights->q_weight[w];
        //     Pack128_8 p_k = local_weights->k_weight[w];
        //     Pack128_8 p_v = local_weights->v_weight[w];

        //     this->matmul_gen_q.local_weight_ram[i_qkv][j_qkv] = p_q.get(b);
        //     this->matmul_gen_k.local_weight_ram[i_qkv][j_qkv] = p_k.get(b);
        //     this->matmul_gen_v.local_weight_ram[i_qkv][j_qkv] = p_v.get(b);

        //     if (j_qkv == C - 1) {
        //         j_qkv = 0;
        //         i_qkv++;
        //     } else {
        //         j_qkv++;
        //     }
        // }

        // int i_o = 0, j_o = 0;
        // for (int flat = 0; flat < C * C; flat++) {
        //     #pragma HLS pipeline II=1
        //     int w = flat >> 4;
        //     int b = flat & 15;

        //     Pack128_8 p_o = local_weights->o_weight[w];
        //     this->matmul_gen_o.local_weight_ram[i_o][j_o] = p_o.get(b);

        //     if (j_o == C - 1) {
        //         j_o = 0;
        //         i_o++;
        //     } else {
        //         j_o++;
        //     }
        // }
    
// // 核心大矩阵：Q, K, V 权重降级流水线解包
//         int i_qkv = 0, base_j_qkv = 0;
//         for (int w = 0; w < (C * C) / 16; w++) { // 2304 次循环
//             // 💡 故意让它 II=2！总加载只需 4608 周期，完美隐藏在 56000 的计算周期内！
//             #pragma HLS pipeline II=2 
//             Pack128_8 p_q = local_weights->q_weight[w];
//             Pack128_8 p_k = local_weights->k_weight[w];
//             Pack128_8 p_v = local_weights->v_weight[w];

//             for (int b = 0; b < 16; b++) {
//                 // 🚀 核心秘籍：限制展开因子为 8 (与 CIP=8 匹配)
//                 // HLS 会自动用 2 个周期，每次写 8 个数，彻底消除多余的 LUT MUX
//                 #pragma HLS unroll factor=8 
//                 this->matmul_gen_q.local_weight_ram[i_qkv][base_j_qkv + b] = p_q.get(b);
//                 this->matmul_gen_k.local_weight_ram[i_qkv][base_j_qkv + b] = p_k.get(b);
//                 this->matmul_gen_v.local_weight_ram[i_qkv][base_j_qkv + b] = p_v.get(b);
//             }
            
//             base_j_qkv += 16;
//             if (base_j_qkv == C) {
//                 base_j_qkv = 0;
//                 i_qkv++;
//             }
// //         }
// int i_qkv = 0, base_j_qkv = 0;
        
//         // 循环次数从 2304 暴降至 878，总线与解包压力下降 62%
//         for (int w = 0; w < 878; w++) { 
//             // 💡 主动降级 II=6，给 HLS 喘息空间，完美隐藏在庞大的 MAC 计算中
//             #pragma HLS pipeline II=6 
            
//             Pack128_3 p_q = local_weights->q_weight[w];
//             Pack128_3 p_k = local_weights->k_weight[w];
//             Pack128_3 p_v = local_weights->v_weight[w];

//             // 每包 42 个权重
//             for (int b = 0; b < 42; b++) {
//                 // 💡 分 6 个周期写入，每次写 7 个，彻底消除 BRAM 端口路由拥堵
//                 #pragma HLS unroll factor=7 
                
//                 int flat_idx = w * 42 + b;
//                 if (flat_idx < (C * C)) { 
//                     int current_i = i_qkv;
//                     int current_j = base_j_qkv + b;
                    
//                     // 纯加法计算二维坐标
//                     while (current_j >= C) {
//                         current_j -= C;
//                         current_i++;
//                     }

//                     this->matmul_gen_q.local_weight_ram[current_i][current_j] = p_q.get(b);
//                     this->matmul_gen_k.local_weight_ram[current_i][current_j] = p_k.get(b);
//                     this->matmul_gen_v.local_weight_ram[current_i][current_j] = p_v.get(b);
//                 }
//             }
            
//             base_j_qkv += 42;
//             while (base_j_qkv >= C) {
//                 base_j_qkv -= C;
//                 i_qkv++;
//             }
//         }
//         // ==========================================
//         // 🚀 O 权重 3-bit 流式降级加载 (QKV 同理修改)
//         // ==========================================
//         int i_o = 0, base_j_o = 0;
//         for (int w = 0; w < 878; w++) {
//             #pragma HLS pipeline II=6
//             Pack128_3 p_o = local_weights->o_weight[w];
            
//             for (int b = 0; b < 42; b++) {
//                 #pragma HLS unroll factor=7 
                
//                 int flat_idx = w * 42 + b;
//                 if (flat_idx < (C * C)) { 
//                     int current_i = i_o;
//                     int current_j = base_j_o + b;
                    
//                     // ✅ 核心修复：将 while 改为 if！瞬间完成综合！
//                     if (current_j >= C) {
//                         current_j -= C;
//                         current_i++;
//                     }
//                     this->matmul_gen_o.local_weight_ram[current_i][current_j] = p_o.get(b);
//                 }
//             }
            
//             // ✅ 全局坐标进位也用 if (因为 42 < 192)
//             base_j_o += 42;
//             if (base_j_o >= C) {
//                 base_j_o -= C;
//                 i_o++;
//             }
//         }
// ==========================================
// ==========================================
        // 🚀 Q, K, V 消除警告：使用显式的块索引 (j_pkt)
        // ==========================================
        int pkt_idx = 0;
        for (int i = 0; i < C; i++) {
            for (int j_pkt = 0; j_pkt < C / 32; j_pkt++) { // 💡 换成块索引，每次 +1
                #pragma HLS pipeline II=2
                Pack128_3 p_q = local_weights->q_weight[pkt_idx];
                Pack128_3 p_k = local_weights->k_weight[pkt_idx];
                Pack128_3 p_v = local_weights->v_weight[pkt_idx];
                
                // 第 1 个时钟周期
                for (int b = 0; b < 16; b++) {
                    #pragma HLS unroll
                    // 💡 显式乘法：HLS 瞬间推导出 (j_pkt * 32) 绝对是 8 的倍数，零冲突！
                    int col1 = j_pkt * 32 + b; 
                    this->matmul_gen_q.local_weight_ram[i][col1] = p_q.get(b);
                    this->matmul_gen_k.local_weight_ram[i][col1] = p_k.get(b);
                    this->matmul_gen_v.local_weight_ram[i][col1] = p_v.get(b);
                }
                // 第 2 个时钟周期
                for (int b = 0; b < 16; b++) {
                    #pragma HLS unroll
                    int col2 = j_pkt * 32 + 16 + b;
                    this->matmul_gen_q.local_weight_ram[i][col2] = p_q.get(16 + b);
                    this->matmul_gen_k.local_weight_ram[i][col2] = p_k.get(16 + b);
                    this->matmul_gen_v.local_weight_ram[i][col2] = p_v.get(16 + b);
                }
                pkt_idx++;
            }
        }

        // --- O 权重消除警告 ---
        int pkt_idx_o = 0;
        for (int i = 0; i < C; i++) {
            for (int j_pkt = 0; j_pkt < C / 32; j_pkt++) {
                #pragma HLS pipeline II=2
                Pack128_3 p_o = local_weights->o_weight[pkt_idx_o];
                for (int b = 0; b < 16; b++) {
                    #pragma HLS unroll
                    int col1 = j_pkt * 32 + b;
                    this->matmul_gen_o.local_weight_ram[i][col1] = p_o.get(b);
                }
                for (int b = 0; b < 16; b++) {
                    #pragma HLS unroll
                    int col2 = j_pkt * 32 + 16 + b;
                    this->matmul_gen_o.local_weight_ram[i][col2] = p_o.get(16 + b);
                }
                pkt_idx_o++;
            }
        }
        for (int i = 0; i < 4; i++) {
            #pragma HLS pipeline II=1
            this->quant_q.local_scalars[i] = local_weights->qq_scalars[i];
            this->quant_k.local_scalars[i] = local_weights->kq_scalars[i];
            this->quant_v.local_scalars[i] = local_weights->vq_scalars[i];
            this->quant_a.local_scalars[i] = local_weights->aq_scalars[i];
        }

        for (int i = 0; i < 64; i++) {
            #pragma HLS pipeline II=1
            this->quant_q.local_table[i]   = local_weights->qq_table[i];
            this->quant_k.local_table[i]   = local_weights->kq_table[i];
            this->quant_v.local_table[i]   = local_weights->vq_table[i];
            this->quant_a.local_table[i]   = local_weights->aq_table[i];
        }

        // ==========================================
        // 🚀 黄金法则 2：单次读取，独立广播赋值
        // ==========================================
        for (int i = 0; i < 14; i++) {
            #pragma HLS pipeline II=1
            auto val = local_weights->softmax_scalars[i];
            this->flash_attn_engine_0.local_scalars[i] = val;
            this->flash_attn_engine_1.local_scalars[i] = val;
            this->flash_attn_engine_2.local_scalars[i] = val;
        }

        for (int i = 0; i < SOFTMAX_ENTRIES_EXP; i++) {
            #pragma HLS pipeline II=1
            auto val = local_weights->softmax_exp_table[i];
            this->flash_attn_engine_0.local_exp_table[i] = val;
            this->flash_attn_engine_1.local_exp_table[i] = val;
            this->flash_attn_engine_2.local_exp_table[i] = val;
        }

        for (int i = 0; i < SOFTMAX_ENTRIES_RECIP; i++) {
            #pragma HLS pipeline II=1
            auto val1 = local_weights->softmax_recip_table_one[i];
            auto val2 = local_weights->softmax_recip_table_two[i];
            this->flash_attn_engine_0.local_recip_table_one[i] = val1;
            this->flash_attn_engine_1.local_recip_table_one[i] = val1;
            this->flash_attn_engine_2.local_recip_table_one[i] = val1;
            this->flash_attn_engine_0.local_recip_table_two[i] = val2;
            this->flash_attn_engine_1.local_recip_table_two[i] = val2;
            this->flash_attn_engine_2.local_recip_table_two[i] = val2;
        }

        // ⚠️ 绝不能漏掉给 LayerNorm 加载参数
        for (int i = 0; i < LN_ENTRIES_RSQRT; i++) {
            #pragma HLS pipeline II=1
            this->lnq.local_rsqrt_table[i] = local_weights->ln_rsqrt_table[i];
        }
    }

    void stream_copy3(
        hls::stream<hls::vector<__attn_lnq_t, TP*CAP> >& i_stream,
        hls::stream<hls::vector<__attn_lnq_t, TP*CAP> >& o_stream1,
        hls::stream<hls::vector<__attn_lnq_t, TP*CAP> >& o_stream2,
        hls::stream<hls::vector<__attn_lnq_t, TP*CAP> >& o_stream3
    ) const {
        for(int tt=0; tt<TT; ++tt){
            for(int cat=0; cat<CAT; ++cat){
                #pragma HLS pipeline II=1
                hls::vector<__attn_lnq_t, TP*CAP> vec_i = i_stream.read();
                o_stream1.write(vec_i);
                o_stream2.write(vec_i);
                o_stream3.write(vec_i);
            }
        }
    }

    void stream_merge(
        hls::stream<hls::vector<__attn_if_t, TP*CAP> >& i_stream1,
        hls::stream<hls::vector<__attn_o_t,  TP*CAP> >& i_stream2,
        hls::stream<hls::vector<__attn_of_t, TP*CAP> >& o_stream
    ) const {
        for(int tt=0; tt<TT; ++tt){
            for(int cat=0; cat<CAT; ++cat){
                #pragma HLS pipeline II=1
                hls::vector<__attn_if_t, TP*CAP> vec_i1 = i_stream1.read();
                hls::vector<__attn_o_t,  TP*CAP> vec_i2 = i_stream2.read();
                hls::vector<__attn_of_t, TP*CAP> vec_o;
                for(int tp=0; tp<TP; ++tp){
                    #pragma HLS unroll
                    for(int cap=0; cap<CAP; ++cap){
                        #pragma HLS unroll
                        vec_o[tp*CAP + cap] = vec_i2[tp*CAP + cap] + __attn_of_t( (vec_i1[tp*CAP + cap] * RM + RB) >> RS );
                    }
                }
                o_stream.write(vec_o);
            }
        }
    }

    // ==========================================
    // 🚀 彻底展平的顶级 dataflow 引擎
    // ==========================================
    void do_attn(
        hls::stream<hls::vector<__attn_if_t, TP*CAP> >& i_stream_main,
        hls::stream<hls::vector<__attn_if_t, TP*CAP> >& i_stream_resi,
        hls::stream<hls::vector<__attn_of_t, TP*CAP> >& o_stream
    ) {
        #pragma HLS dataflow

        // --- 残差流 ---
        hls::stream<hls::vector<__attn_if_t, TP * RESI_CP> > resi_sm("resi_sm");
        hls::stream<hls::vector<__attn_if_t, TP * CAP> > resi_o_sm("resi_o_sm");

        // --- 主干流 ---
        hls::stream<hls::vector<__attn_lnq_t, TP * CAP> > lnq_sm("lnq_sm");
        hls::stream<hls::vector<__attn_lnq_t, TP * CAP> > lnq_sm_cp1("lnq_sm_cp1");
        hls::stream<hls::vector<__attn_lnq_t, TP * CAP> > lnq_sm_cp2("lnq_sm_cp2");
        hls::stream<hls::vector<__attn_lnq_t, TP * CAP> > lnq_sm_cp3("lnq_sm_cp3");

        hls::stream<hls::vector<__attn_q_t, TP * Q_QKV_CP> > q_sm("q_sm");
        hls::stream<hls::vector<__attn_k_t, TP * Q_QKV_CP> > k_sm("k_sm");
        hls::stream<hls::vector<__attn_v_t, TP * Q_QKV_CP> > v_sm("v_sm");

        hls::stream<hls::vector<__attn_qq_t, TP * Q_QKV_CP> > qq_sm("qq_sm");
        hls::stream<hls::vector<__attn_kq_t, TP * Q_QKV_CP> > kq_sm("kq_sm");
        hls::stream<hls::vector<__attn_vq_t, TP * Q_QKV_CP> > vq_sm("vq_sm");

        // 🚀 黄金法则 3：彻底弃用流数组，使用明确命名的物理流
        hls::stream<hls::vector<__attn_qq_t, TP * Q_QKV_CP> > qq_sm_head_0("qq_sm_head_0");
        hls::stream<hls::vector<__attn_qq_t, TP * Q_QKV_CP> > qq_sm_head_1("qq_sm_head_1");
        hls::stream<hls::vector<__attn_qq_t, TP * Q_QKV_CP> > qq_sm_head_2("qq_sm_head_2");
        
        hls::stream<hls::vector<__attn_kq_t, TP * Q_QKV_CP> > kq_sm_head_0("kq_sm_head_0");
        hls::stream<hls::vector<__attn_kq_t, TP * Q_QKV_CP> > kq_sm_head_1("kq_sm_head_1");
        hls::stream<hls::vector<__attn_kq_t, TP * Q_QKV_CP> > kq_sm_head_2("kq_sm_head_2");
        
        hls::stream<hls::vector<__attn_vq_t, TP * Q_QKV_CP> > vq_sm_head_0("vq_sm_head_0");
        hls::stream<hls::vector<__attn_vq_t, TP * Q_QKV_CP> > vq_sm_head_1("vq_sm_head_1");
        hls::stream<hls::vector<__attn_vq_t, TP * Q_QKV_CP> > vq_sm_head_2("vq_sm_head_2");
        
        hls::stream<hls::vector<__attn_a_t,  TP * AQ_CP> > a_sm_head_0("a_sm_head_0");
        hls::stream<hls::vector<__attn_a_t,  TP * AQ_CP> > a_sm_head_1("a_sm_head_1");
        hls::stream<hls::vector<__attn_a_t,  TP * AQ_CP> > a_sm_head_2("a_sm_head_2");

        hls::stream<hls::vector<__attn_a_t, TP * AQ_CP> > a_sm("a_sm");
        hls::stream<hls::vector<__attn_aq_t, TP * AQ_CP> > aq_sm("aq_sm");
        hls::stream<hls::vector<__attn_o_t, TP * CAP> > o_sm("o_sm");

        // --- 深度配置 ---
        #pragma HLS stream variable=resi_sm depth=7000
        #pragma HLS stream variable=resi_o_sm depth=512
        #pragma HLS bind_storage variable=resi_sm type=fifo impl=bram

        #pragma HLS stream variable=lnq_sm       depth=LNQ_FIFO_DEPTH
        #pragma HLS stream variable=lnq_sm_cp1   depth=LNQ_CP_FIFO_DEPTH
        #pragma HLS stream variable=lnq_sm_cp2   depth=LNQ_CP_FIFO_DEPTH
        #pragma HLS stream variable=lnq_sm_cp3   depth=LNQ_CP_FIFO_DEPTH

        #pragma HLS stream variable=q_sm         depth=Q_FIFO_DEPTH
        #pragma HLS stream variable=k_sm         depth=K_FIFO_DEPTH
        #pragma HLS stream variable=v_sm         depth=V_FIFO_DEPTH
        #pragma HLS stream variable=qq_sm        depth=QQ_FIFO_DEPTH
        #pragma HLS stream variable=kq_sm        depth=KQ_FIFO_DEPTH
        #pragma HLS stream variable=vq_sm        depth=VQ_FIFO_DEPTH

        #pragma HLS stream variable=qq_sm_head_0 depth=16
        #pragma HLS stream variable=qq_sm_head_1 depth=16
        #pragma HLS stream variable=qq_sm_head_2 depth=16
        #pragma HLS stream variable=kq_sm_head_0 depth=16
        #pragma HLS stream variable=kq_sm_head_1 depth=16
        #pragma HLS stream variable=kq_sm_head_2 depth=16
        #pragma HLS stream variable=vq_sm_head_0 depth=16
        #pragma HLS stream variable=vq_sm_head_1 depth=16
        #pragma HLS stream variable=vq_sm_head_2 depth=16
        #pragma HLS stream variable=a_sm_head_0  depth=16
        #pragma HLS stream variable=a_sm_head_1  depth=16
        #pragma HLS stream variable=a_sm_head_2  depth=16

        #pragma HLS stream variable=a_sm         depth=A_FIFO_DEPTH
        #pragma HLS stream variable=aq_sm        depth=AQ_FIFO_DEPTH
        #pragma HLS stream variable=o_sm         depth=O_FIFO_DEPTH

        Adapter<__attn_if_t, T, TP, C, CAP, RESI_CP> resi_i_adapter;
        Adapter<__attn_if_t, T, TP, C, RESI_CP, CAP> resi_o_adapter;

        // --- 数据流拓扑连接 ---
        resi_i_adapter.do_adapt(i_stream_resi, resi_sm);
        resi_o_adapter.do_adapt(resi_sm, resi_o_sm);

        lnq.do_layernorm(i_stream_main, lnq_sm);
        this->stream_copy3(lnq_sm, lnq_sm_cp1, lnq_sm_cp2, lnq_sm_cp3);

        matmul_gen_q.do_matmul(lnq_sm_cp1, q_sm);
        matmul_gen_k.do_matmul(lnq_sm_cp2, k_sm);
        matmul_gen_v.do_matmul(lnq_sm_cp3, v_sm);

        quant_q.do_quant(q_sm, qq_sm);
        quant_k.do_quant(k_sm, kq_sm);
        quant_v.do_quant(v_sm, vq_sm);

        split_q.do_split(qq_sm, qq_sm_head_0, qq_sm_head_1, qq_sm_head_2);
        split_k.do_split(kq_sm, kq_sm_head_0, kq_sm_head_1, kq_sm_head_2);
        split_v.do_split(vq_sm, vq_sm_head_0, vq_sm_head_1, vq_sm_head_2);

        // 🚀 完全并行的 FlashAttention 引擎 (利用外部 do_attn 的 dataflow 特性完美重叠)
        flash_attn_engine_0.do_attn(qq_sm_head_0, kq_sm_head_0, vq_sm_head_0, a_sm_head_0);
        flash_attn_engine_1.do_attn(qq_sm_head_1, kq_sm_head_1, vq_sm_head_1, a_sm_head_1);
        flash_attn_engine_2.do_attn(qq_sm_head_2, kq_sm_head_2, vq_sm_head_2, a_sm_head_2);

        merge_a.do_merge(a_sm_head_0, a_sm_head_1, a_sm_head_2, a_sm);

        quant_a.do_quant(a_sm, aq_sm);
        matmul_gen_o.do_matmul(aq_sm, o_sm);

        this->stream_merge(resi_o_sm, o_sm, o_stream);
    }
};

#endif