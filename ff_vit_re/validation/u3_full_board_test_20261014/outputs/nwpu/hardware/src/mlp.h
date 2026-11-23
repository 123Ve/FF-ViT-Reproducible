#ifndef __INT_MLP_H__
#define __INT_MLP_H__

#include "common.h"
#include "layernorm.h"
#include "matmul.h"
#include "gelu.h"
#include "utils.h"
#include "dataflow.h" // 确保引入了 MlpLayerWeights 的定义

using namespace std;

template<

    // mlp                                  
    int     T,                  // input  feature map sequence length, shared by all layers
    int     TP,                 // input  feature map sequence parallel degree
    int     C,                  // input & output feature map channels
    int     CAP,                // input & output feature map channel adaptive parallel degree
    int     RESI_CP,            // residual branch channel parallel degree
    int     CH,                 // hidden feature map channels
    int     CHAP,               // hidden feature map channel adaptive parallel degree, shared by gelu

    class   __mlp_if_t,         // input feature map type
    class   __mlp_ln_t,         // layernorm type
    class   __mlp_m1_t,         // mac type
    class   __mlp_ge_t,         // gelu type
    class   __mlp_m2_t,         // mac type
    class   __mlp_of_t,         // output feature map type

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

    // matmul 1
    class   __m1_we_t,          // weight type
    class   __m1_bi_t,
    class   __m1_mc_t,          // mac type
    int     M1_CIP,             // input  feature map channel parallel degree
    int     M1_COP,             // output feature map channel parallel degree
    int     M1_ADPT_FIFO_DEPTH, // adapter fifo depthmlp
    int     M1_WIND_FIFO_DEPTH, // cache window fifo depth
    int     M1_WGHT_FIFO_DEPTH, // weight fifo depth
    int     M1_MACS_FIFO_DEPTH, // mac fifo depth
    bool    M1_USE_DSP,         // use DSP or not

    // gelu
    class   __gelu_cursor_t,    // lookup table cursor type
    int     GELU_ENTRIES,

    // matmul 2
    class   __m2_we_t,          // weight type
    class   __m2_bi_t,
    class   __m2_mc_t,          // mac type
    int     M2_CIP,             // input  feature map channel parallel degree
    int     M2_COP,             // output feature map channel parallel degree
    int     M2_ADPT_FIFO_DEPTH, // adapter fifo depth
    int     M2_WIND_FIFO_DEPTH, // cache window fifo depth
    int     M2_WGHT_FIFO_DEPTH, // weight fifo depth
    int     M2_MACS_FIFO_DEPTH, // mac fifo depth
    bool    M2_USE_DSP          // use DSP or not
> class MLP{
public:

    // static assertions
    static_assert(  C   % CAP      == 0, "C must be multiple of CAP");
    static_assert(  CH  % CHAP     == 0, "CH must be multiple of CHAP");
    static_assert(  T   % TP       == 0, "T must be multiple of TP");
    static_assert(  C   % M1_CIP   == 0, "C must be multiple of M1_CIP");
    static_assert(  CH  % M1_COP   == 0, "CH must be multiple of M1_COP");
    static_assert(  CH  % M2_CIP   == 0, "CH must be multiple of M2_CIP");
    static_assert(  C   % M2_COP   == 0, "C must be multiple of M2_COP");

    // static hyper parameters
    static constexpr int TT  = T    / TP;
    static constexpr int CAT = C    / CAP;

    // scalar weights
    int RM, RS, RB;

    // components
    Layernorm<
        __mlp_if_t, __ln_sum_t, __ln_divc_t, __ln_mu_t, __ln_var_t, __ln_cursor_t,
        __ln_rsqrt_t, __ln_affine_t, __ln_shift_t, __mlp_ln_t, LN_ENTRIES_RSQRT,
        T, TP, C, CAP
    > lnq;

    Matmul<
        __mlp_ln_t, __m1_we_t, __m1_bi_t, __mlp_m1_t,
        T, TP, C, M1_CIP, CAP, CH, M1_COP, CHAP,
        M1_ADPT_FIFO_DEPTH, M1_WIND_FIFO_DEPTH, M1_WGHT_FIFO_DEPTH, M1_MACS_FIFO_DEPTH,
        LRAM_STYLE, M1_USE_DSP
    > m1;

    GeLU<
        __mlp_m1_t, __gelu_cursor_t, __mlp_ge_t,
        T, TP, CH, CHAP, GELU_ENTRIES
    > ge;

    Matmul<
        __mlp_ge_t, __m2_we_t, __m2_bi_t, __mlp_m2_t,
        T, TP, CH, M2_CIP, CHAP, C, M2_COP, CAP,
        M2_ADPT_FIFO_DEPTH, M2_WIND_FIFO_DEPTH, M2_WGHT_FIFO_DEPTH, M2_MACS_FIFO_DEPTH,
        LRAM_STYLE, M2_USE_DSP
    > m2;

    // ==========================================
    // 💥 修复后的无参构造函数
    // ==========================================
    explicit MLP() :
        lnq (),
        m1  (),
        ge  (),
        m2  ()
    {
        // 构造函数完全留空。
        // 所有标量和内存的初始化都交由下面的 load_weights_from_bram 动态完成
    }

    void load_weights_from_bram(const MlpLayerWeights* local_weights) {
            #pragma HLS inline

            this->RM = local_weights->mlp_scalars[0];
            this->RS = local_weights->mlp_scalars[1];
            this->RB = (this->RS > 0) ? (1 << (this->RS - 1)) : 0;

            for (int i = 0; i < 7; i++) {
				#pragma HLS pipeline II=1
                this->lnq.local_scalars[i] = local_weights->ln_scalars[i];
            }

            // ==========================================
                    // 1 & 2. 偏置与 LN 加载
                    // ==========================================
                    int i_b_m2 = 0;
                    for (int w = 0; w < C / 8; w++) { // 192 / 8 = 24 块
                        Pack128_16 p_m2 = local_weights->m2_bias[w];
                        for (int b = 0; b < 8; b++) {
                            #pragma HLS pipeline II=1
                            this->m2.local_bias_ram[i_b_m2] = p_m2.get(b);
                            this->lnq.local_lnw_ram[i_b_m2] = local_weights->ln_lnw[i_b_m2];
                            this->lnq.local_lnb_ram[i_b_m2] = local_weights->ln_lnb[i_b_m2];
                            i_b_m2++;
                        }
                    }

                    int i_b_m1 = 0;
                    for (int w = 0; w < CH / 8; w++) { // 768 / 8 = 96 块
                        Pack128_16 p_m1 = local_weights->m1_bias[w];
                        for (int b = 0; b < 8; b++) {
                            #pragma HLS pipeline II=1
                            this->m1.local_bias_ram[i_b_m1] = p_m1.get(b);
                            i_b_m1++;
                        }
                    }

                    // // ==========================================
                    // // 3. 核心大矩阵：M1, M2 流式解包
                    // // ==========================================

                    // // --- M1 权重加载 (外形：CH x C) ---
                    // int i_m1 = 0, j_m1 = 0;
                    // for (int w = 0; w < (CH * C) / 16; w++) { // 9216 块
                    //     Pack128_8 p_m1 = local_weights->m1_weight[w];
                    //     for (int b = 0; b < 16; b++) {
                    //         #pragma HLS pipeline II=1
                    //         this->m1.local_weight_ram[i_m1][j_m1] = p_m1.get(b);

                    //         j_m1++;
                    //         if (j_m1 == C) {
                    //             j_m1 = 0;
                    //             i_m1++;
                    //         }
                    //     }
                    // }

                    // // --- M2 权重加载 (外形：C x CH) ---
                    // int i_m2 = 0, j_m2 = 0;
                    // for (int w = 0; w < (C * CH) / 16; w++) { // 9216 块
                    //     Pack128_8 p_m2 = local_weights->m2_weight[w];
                    //     for (int b = 0; b < 16; b++) {
                    //         #pragma HLS pipeline II=1
                    //         this->m2.local_weight_ram[i_m2][j_m2] = p_m2.get(b);

                    //         j_m2++;
                    //         if (j_m2 == CH) {
                    //             j_m2 = 0;
                    //             i_m2++;
                    //         }
                    //     }
                    // }
                    // ==========================================


// ==========================================
        // 3. 核心大矩阵：M1, M2 主动降级流水线解包 (彻底消除 II 警告并省资源)
        // ==========================================

        // // --- M1 权重加载 (外形：CH x C) ---
        // int i_m1 = 0, base_j_m1 = 0;
        // for (int w = 0; w < (CH * C) / 16; w++) { // 9216 块
        //     // 💡 核心 1：主动要求 II=2。总计 1.8 万周期，完美隐藏在 5.6 万计算周期内
        //     #pragma HLS pipeline II=2
        //     Pack128_8 p_m1 = local_weights->m1_weight[w];
            
        //     for (int b = 0; b < 16; b++) {
        //         // 💡 核心 2：每次只并行处理 8 个元素，分 2 个周期写完 16 个数
        //         // 这将极大缓解 BRAM 端口拥堵和 LUT 路由压力
        //         #pragma HLS unroll factor=8 
        //         this->m1.local_weight_ram[i_m1][base_j_m1 + b] = p_m1.get(b);
        //     }
            
        //     base_j_m1 += 16;
        //     if (base_j_m1 == C) { 
        //         base_j_m1 = 0;
        //         i_m1++;
        //     }
        // }

        // // --- M2 权重加载 (外形：C x CH) ---
        // int i_m2 = 0, base_j_m2 = 0;
        // for (int w = 0; w < (C * CH) / 16; w++) { // 9216 块
        //     // 💡 同样主动声明 II=2
        //     #pragma HLS pipeline II=2
        //     Pack128_8 p_m2 = local_weights->m2_weight[w];
            
        //     for (int b = 0; b < 16; b++) {
        //         #pragma HLS unroll factor=8
        //         this->m2.local_weight_ram[i_m2][base_j_m2 + b] = p_m2.get(b);
        //     }
            
        //     base_j_m2 += 16;
        //     if (base_j_m2 == CH) { 
        //         base_j_m2 = 0;
        //         i_m2++;
        //     }
        // }
        //     // --- M1 权重加载 (外形：CH x C, 即 768 x 192) ---
        // int i_m1 = 0, base_j_m1 = 0;
        // for (int w = 0; w < 3511; w++) { 
        //     #pragma HLS pipeline II=6 
        //     Pack128_3 p_m1 = local_weights->m1_weight[w];
            
        //     for (int b = 0; b < 42; b++) {
        //         #pragma HLS unroll factor=7 
                
        //         int flat_idx = w * 42 + b;
        //         if (flat_idx < (CH * C)) {
        //             int current_i = i_m1;
        //             int current_j = base_j_m1 + b;
                    
        //             // ✅ 核心修复：M1 换行 (列数是 C)
        //             if (current_j >= C) {
        //                 current_j -= C;
        //                 current_i++;
        //             }
        //             this->m1.local_weight_ram[current_i][current_j] = p_m1.get(b);
        //         }
        //     }
            
        //     base_j_m1 += 42;
        //     if (base_j_m1 >= C) { 
        //         base_j_m1 -= C;
        //         i_m1++;
        //     }
        // }

        // // --- M2 权重加载 (外形：C x CH, 即 192 x 768) ---
        // int i_m2 = 0, base_j_m2 = 0;
        // for (int w = 0; w < 3511; w++) { 
        //     #pragma HLS pipeline II=6
        //     Pack128_3 p_m2 = local_weights->m2_weight[w];
            
        //     for (int b = 0; b < 42; b++) {
        //         #pragma HLS unroll factor=7
                
        //         int flat_idx = w * 42 + b;
        //         if (flat_idx < (C * CH)) {
        //             int current_i = i_m2;
        //             int current_j = base_j_m2 + b;
                    
        //             // ✅ 核心修复：M2 换行 (列数是 CH)
        //             if (current_j >= CH) {
        //                 current_j -= CH;
        //                 current_i++;
        //             }
        //             this->m2.local_weight_ram[current_i][current_j] = p_m2.get(b);
        //         }
        //     }
            
        //     base_j_m2 += 42;
        //     if (base_j_m2 >= CH) { 
        //         base_j_m2 -= CH;
        //         i_m2++;
        //     }
        // } 
        // ==========================================
        // 🚀 M1, M2 核心权重 3-bit 加载 (双端口极限压榨)
        // ==========================================

// ==========================================
        // 🚀 M1, M2 对齐解包 (9216 周期跑完 14.7 万数据！)
        // ==========================================
// ==========================================
        // 🚀 M1, M2 消除警告
        // ==========================================

        // M1: 768 x 192 (列宽是 C)
        int pkt_idx_m1 = 0;
        for (int i = 0; i < CH; i++) {
            for (int j_pkt = 0; j_pkt < C / 32; j_pkt++) {
                #pragma HLS pipeline II=2
                Pack128_3 p_m1 = local_weights->m1_weight[pkt_idx_m1];
                for (int b = 0; b < 16; b++) {
                    #pragma HLS unroll
                    int col1 = j_pkt * 32 + b;
                    this->m1.local_weight_ram[i][col1] = p_m1.get(b);
                }
                for (int b = 0; b < 16; b++) {
                    #pragma HLS unroll
                    int col2 = j_pkt * 32 + 16 + b;
                    this->m1.local_weight_ram[i][col2] = p_m1.get(16 + b);
                }
                pkt_idx_m1++;
            }
        }

        // M2: 192 x 768 (列宽是 CH)
        int pkt_idx_m2 = 0;
        for (int i = 0; i < C; i++) {
            for (int j_pkt = 0; j_pkt < CH / 32; j_pkt++) {
                #pragma HLS pipeline II=2
                Pack128_3 p_m2 = local_weights->m2_weight[pkt_idx_m2];
                for (int b = 0; b < 16; b++) {
                    #pragma HLS unroll
                    int col1 = j_pkt * 32 + b;
                    this->m2.local_weight_ram[i][col1] = p_m2.get(b);
                }
                for (int b = 0; b < 16; b++) {
                    #pragma HLS unroll
                    int col2 = j_pkt * 32 + 16 + b;
                    this->m2.local_weight_ram[i][col2] = p_m2.get(16 + b);
                }
                pkt_idx_m2++;
            }
        } 
            // ==========================================
            // 4. GeLU 与 LayerNorm 查表
            // ==========================================
            for(int i = 0; i < 4; i++) {
				#pragma HLS pipeline II=1
                this->ge.local_scalars[i] = local_weights->ge_scalars[i];
            }
            for(int i = 0; i < 64; i++) {
                #pragma HLS pipeline II=1
                this->ge.local_table[i] = local_weights->ge_table[i];
            }
            for (int i = 0; i < LN_ENTRIES_RSQRT; i++) {
                #pragma HLS pipeline II=1
                this->lnq.local_rsqrt_table[i] = local_weights->ln_rsqrt_table[i];
            }
        }

    void stream_copy(
        hls::stream<hls::vector<__mlp_if_t, TP*CAP> >& i_stream,
        hls::stream<hls::vector<__mlp_if_t, TP*CAP> >& o_stream1,
        hls::stream<hls::vector<__mlp_if_t, TP*CAP> >& o_stream2
    ) const {
        for(int tt=0; tt<TT; ++tt){
            for(int cat=0; cat<CAT; ++cat){
                #pragma HLS pipeline II=1

                hls::vector<__mlp_if_t, TP*CAP> vec_i = i_stream.read();
                o_stream1.write(vec_i);
                o_stream2.write(vec_i);

            } // end of CAT_LOOP
        } // end of TT_LOOP
    }

    void stream_merge(
        hls::stream<hls::vector<__mlp_if_t, TP*CAP> >& i_stream1, // residual branch
        hls::stream<hls::vector<__mlp_m2_t, TP*CAP> >& i_stream2, // main branch
        hls::stream<hls::vector<__mlp_of_t, TP*CAP> >& o_stream
    ) const {
        for(int tt=0; tt<TT; ++tt){
            for(int cat=0; cat<CAT; ++cat){
                #pragma HLS pipeline II=1

                hls::vector<__mlp_if_t, TP*CAP> vec_i1 = i_stream1.read();
                hls::vector<__mlp_m2_t, TP*CAP> vec_i2 = i_stream2.read();
                hls::vector<__mlp_of_t, TP*CAP> vec_o;

                for(int tp=0; tp<TP; ++tp){
                    #pragma HLS unroll
                    for(int cap=0; cap<CAP; ++cap){
                        #pragma HLS unroll
                        vec_o[tp*CAP + cap] = vec_i2[tp*CAP + cap] + __mlp_of_t( (vec_i1[tp*CAP + cap] * RM + RB) >> RS );
                    }
                }

                o_stream.write(vec_o);

            } // end of CAT_LOOP
        } // end of TT_LOOP
    }

    void do_mlp(
        hls::stream<hls::vector<__mlp_if_t, TP*CAP> >& i_stream,
        hls::stream<hls::vector<__mlp_of_t, TP*CAP> >& o_stream
    ) {

        #pragma HLS dataflow

        hls::stream<hls::vector<__mlp_if_t,     TP* CAP         > > main_sm;
        hls::stream<hls::vector<__mlp_if_t,     TP* CAP         > > resi_i_sm;
        hls::stream<hls::vector<__mlp_if_t,     TP* RESI_CP     > > resi_sm;
        hls::stream<hls::vector<__mlp_if_t,     TP* CAP         > > resi_o_sm;
        hls::stream<hls::vector<__mlp_ln_t,     TP* CAP         > > ln_sm;
        hls::stream<hls::vector<__mlp_m1_t,     TP* CHAP        > > m1_sm;
        hls::stream<hls::vector<__mlp_ge_t,     TP* CHAP        > > ge_sm;
        hls::stream<hls::vector<__mlp_m2_t,     TP* CAP         > > m2_sm;

        #pragma HLS stream variable=main_sm     depth=2
        #pragma HLS stream variable=resi_i_sm   depth=2
        // 在 mlp.h 中修改：
        #pragma HLS stream variable=resi_sm depth=512
// 深度小于 1024 时，即使不加 bind_storage，HLS 也会智能分配 LUTRAM 或极少 BRAM
        #pragma HLS bind_storage variable=resi_sm type=fifo impl=bram
        #pragma HLS stream variable=resi_o_sm   depth=2
        #pragma HLS stream variable=ln_sm       depth=2
        #pragma HLS stream variable=m1_sm       depth=2
        #pragma HLS stream variable=ge_sm       depth=2
        #pragma HLS stream variable=m2_sm       depth=2

        // two residual related adapters
        Adapter<__mlp_if_t, T, TP, C, CAP, RESI_CP> resi_i_adapter;
        Adapter<__mlp_if_t, T, TP, C, RESI_CP, CAP> resi_o_adapter;

        this->              stream_copy     (   i_stream,   main_sm,    resi_i_sm   );
        resi_i_adapter.     do_adapt        (   resi_i_sm,  resi_sm                 );
        resi_o_adapter.     do_adapt        (   resi_sm,    resi_o_sm               );
        lnq.                do_layernorm_inter_token    (   main_sm,    ln_sm                   );
        m1.                 do_matmul       (   ln_sm,      m1_sm                   );
        ge.                 do_gelu         (   m1_sm,      ge_sm                   );
        m2.                 do_matmul       (   ge_sm,      m2_sm                   );
        this->              stream_merge    (   resi_o_sm,  m2_sm,      o_stream    );

    }

};

#endif
 
