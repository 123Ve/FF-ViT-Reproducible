#ifndef __INT_FUSED_FLASH_ATTN_H__
#define __INT_FUSED_FLASH_ATTN_H__

#include "common.h"
#include "utils.h"

template<
    int     T,
    int     TP,
    int     CH,
    int     Q_QKV_CP,
    int     AQ_CP,
    class   __qq_t,
    class   __kq_t,
    class   __vq_t,
    class   __a_t,
    class   __softmax_minus_t,  
    class   __softmax_cursor1_t,
    class   __softmax_exp_t,
    class   __softmax_acc_t,
    class   __softmax_recip_t,
    class   __softmax_cursor2_one_t,
    class   __softmax_cursor2_two_t,
    class   __softmax_affine_t,
    class   __softmax_cursor3_t,
    int     ENTRIES_EXP,
    int     ENTRIES_RECIP
>
class FlashAttentionHead {
public:
    static constexpr int TT = T / TP;
    static constexpr int CHT_IN = CH / Q_QKV_CP;
    static constexpr int CHT_OUT = CH / AQ_CP;

    int                 local_scalars[14];
    __softmax_exp_t     local_exp_table[ENTRIES_EXP];
    __softmax_recip_t   local_recip_table_one[ENTRIES_RECIP];
    __softmax_recip_t   local_recip_table_two[ENTRIES_RECIP];

    explicit FlashAttentionHead() {}

    void do_attn(
        hls::stream<hls::vector<__qq_t, TP * Q_QKV_CP> >& qq_sm,
        hls::stream<hls::vector<__kq_t, TP * Q_QKV_CP> >& kq_sm,
        hls::stream<hls::vector<__vq_t, TP * Q_QKV_CP> >& vq_sm,
        hls::stream<hls::vector<__a_t,  TP * AQ_CP> >& a_sm
    ) {
        // ==========================================
        // 1. 利用 URAM 存储整头的 Q, K, V
        // ==========================================
        __qq_t Q_buf[T][CH];
        __kq_t K_buf[T][CH];
        __vq_t V_buf[T][CH];
        
        #pragma HLS bind_storage variable=Q_buf type=ram_2p impl=bram
        #pragma HLS bind_storage variable=K_buf type=ram_2p impl=bram
        #pragma HLS bind_storage variable=V_buf type=ram_2p impl=bram
        
        #pragma HLS array_reshape variable=Q_buf dim=2 complete
        #pragma HLS array_reshape variable=K_buf dim=2 complete
        #pragma HLS array_reshape variable=V_buf dim=2 complete

        // Load 阶段：将外部数据写入缓存
        LOAD_LOOP: for(int tt=0; tt<TT; ++tt) {
            for(int ct=0; ct<CHT_IN; ++ct) {
                #pragma HLS pipeline II=1
                auto vec_q = qq_sm.read();
                auto vec_k = kq_sm.read();
                auto vec_v = vq_sm.read();
                
                for(int tp=0; tp<TP; ++tp) {
                    #pragma HLS unroll
                    for(int cp=0; cp<Q_QKV_CP; ++cp) {
                        #pragma HLS unroll
                        int t_idx = tt * TP + tp;
                        int c_idx = ct * Q_QKV_CP + cp;
                        Q_buf[t_idx][c_idx] = vec_q[tp * Q_QKV_CP + cp];
                        K_buf[t_idx][c_idx] = vec_k[tp * Q_QKV_CP + cp];
                        V_buf[t_idx][c_idx] = vec_v[tp * Q_QKV_CP + cp];
                    }
                }
            }
        }

        int b1 = local_scalars[0], s1 = local_scalars[1], bound1 = local_scalars[2];
        int b2_one = local_scalars[3], s2_one = local_scalars[4], bound2_one = local_scalars[5];
        int b3_one = local_scalars[6], s3_one = local_scalars[7];
        int b2_two = local_scalars[8], s2_two = local_scalars[9], bound2_two = local_scalars[10];
        int b3_two = local_scalars[11], s3_two = local_scalars[12], clamp_bits = local_scalars[13];

        // ==========================================
        // 3. Compute 阶段：100% 对齐原设计的 Row-wise 软化
        // ==========================================
        COMPUTE_TT_LOOP: for(int tt=0; tt<TT; ++tt) {

            // // 极简缓存：仅需存当前 TP 个 Token 的 QK 点乘结果 (极省 BRAM)
            // int S_buf[TP][T];
            // #pragma HLS array_partition variable=S_buf dim=1 complete
            // #pragma HLS bind_storage variable=S_buf type=ram_2p impl=bram

            // long long max_val[TP];
            // #pragma HLS array_partition variable=max_val complete
            // for(int tp=0; tp<TP; ++tp) max_val[tp] = -2147483648;

            // // [Pass 1]: 计算 Q*K^T 并同步找最大值
            // PASS1_J_LOOP: for(int j=0; j<T; ++j) {
            //     #pragma HLS pipeline II=1
            //     for(int tp=0; tp<TP; ++tp) {
            //         int i = tt * TP + tp;
            //         long long S_ij = 0;
            //         for(int c=0; c<CH; ++c) {
            //             #pragma HLS unroll
            //             S_ij += Q_buf[i][c] * K_buf[j][c];
            //         }
            //         S_buf[tp][j] = (int)S_ij;
            //         if(S_ij > max_val[tp]) {
            //             max_val[tp] = S_ij;
            //         }
            //     }
            // }

            // // [Pass 2]: 减去最大值查表并累加求和
            // __softmax_acc_t acc_val[TP];
            // #pragma HLS array_partition variable=acc_val complete
            // for(int tp=0; tp<TP; ++tp) acc_val[tp] = 0;

            // PASS2_J_LOOP: for(int j=0; j<T; ++j) {
            //     #pragma HLS pipeline II=1
            //     for(int tp=0; tp<TP; ++tp) {
            //         __softmax_minus_t minus = max_val[tp] - S_buf[tp][j]; 
            //         __softmax_cursor1_t cursor = (minus + b1) >> s1;
            //         cursor = clamp(cursor, 0, bound1);
            //         acc_val[tp] += local_exp_table[cursor];
            //     }
            // }

            // // [Pass 3]: 求最终倒数，归一化，并立刻乘 V
            // __softmax_recip_t recip_val[TP];
            // bool in_two[TP];
            // #pragma HLS array_partition variable=recip_val complete
            // #pragma HLS array_partition variable=in_two complete

            // for(int tp=0; tp<TP; ++tp) {
            //     #pragma HLS unroll
            //     __softmax_cursor2_one_t cursor_one = (acc_val[tp] + b2_one) >> s2_one;
            //     if(cursor_one > bound2_one) {
            //         in_two[tp] = 1;
            //         __softmax_cursor2_two_t cursor_two = (acc_val[tp] + b2_two) >> s2_two;
            //         cursor_two = clamp(cursor_two, 0, bound2_two);
            //         recip_val[tp] = local_recip_table_two[cursor_two];
            //     } else {
            //         in_two[tp] = 0;
            //         cursor_one = clamp(cursor_one, 0, bound2_one);
            //         recip_val[tp] = local_recip_table_one[cursor_one];
            //     }
            // }

            // long long O_acc[TP][CH];
            // #pragma HLS array_partition variable=O_acc complete dim=0
            // for(int tp=0; tp<TP; ++tp) {
            //     #pragma HLS unroll
            //     for(int c=0; c<CH; ++c) {
            //         #pragma HLS unroll
            //         O_acc[tp][c] = 0;
            //     }
            // }

            // PASS3_J_LOOP: for(int j=0; j<T; ++j) {
            //     #pragma HLS pipeline II=1
            //     for(int tp=0; tp<TP; ++tp) {
            //         __softmax_minus_t minus = max_val[tp] - S_buf[tp][j];
            //         __softmax_cursor1_t cursor = (minus + b1) >> s1;
            //         cursor = clamp(cursor, 0, bound1);
            //         __softmax_exp_t exp_val = local_exp_table[cursor];

            //         __softmax_affine_t val = exp_val * recip_val[tp];
                    
            //         int rel_b3 = (in_two[tp] == 1) ? b3_two : b3_one;
            //         int rel_s3 = (in_two[tp] == 1) ? s3_two : s3_one;
            //         __softmax_cursor3_t rel = (val + rel_b3) >> rel_s3;
                    
            //         // 完美还原原有的量化逻辑
            //         int rq_val = quantize_clamp(rel, clamp_bits, false);

            //         for(int c=0; c<CH; ++c) {
            //             #pragma HLS unroll
            //             O_acc[tp][c] += rq_val * V_buf[j][c];
            //         }
            //     }
            // }
            // 💡 核心优化 1：不仅分配 BRAM，还要在维度 2 上切分，支持双口并发写
            int S_buf[TP][T];
            #pragma HLS array_partition variable=S_buf dim=1 complete
            #pragma HLS array_partition variable=S_buf dim=2 cyclic factor=2
            #pragma HLS bind_storage variable=S_buf type=ram_2p impl=bram

            // 💡 核心优化 2：把查表完全打散，支持一周期多次读取
            #pragma HLS array_partition variable=local_exp_table complete

            long long max_val[TP];
            #pragma HLS array_partition variable=max_val complete
            for(int tp=0; tp<TP; ++tp) max_val[tp] = -2147483648;

            // ==========================================
            // [Pass 1]: 一次读两行 K_buf，双口并行算 Q*K^T
            // ==========================================
            PASS1_J_LOOP: for(int j=0; j<T; j+=2) { 
                #pragma HLS pipeline II=1
                for(int tp=0; tp<TP; ++tp) {
                    int i = tt * TP + tp;
                    long long S_ij_0 = 0;
                    long long S_ij_1 = 0;
                    
                    for(int c=0; c<CH; ++c) {
                        #pragma HLS unroll
                        auto q_val = Q_buf[i][c]; // 广播复用
                        S_ij_0 += q_val * K_buf[j][c];
                        S_ij_1 += q_val * K_buf[j+1][c];
                    }
                    S_buf[tp][j]   = (int)S_ij_0;
                    S_buf[tp][j+1] = (int)S_ij_1;
                    
                    // 局部归约最大值
                    long long local_max = (S_ij_0 > S_ij_1) ? S_ij_0 : S_ij_1;
                    if(local_max > max_val[tp]) {
                        max_val[tp] = local_max;
                    }
                }
            }

            __softmax_acc_t acc_val[TP];
            #pragma HLS array_partition variable=acc_val complete
            for(int tp=0; tp<TP; ++tp) acc_val[tp] = 0;

            // ==========================================
            // [Pass 2]: 一周期并行查两次指数表
            // ==========================================
            PASS2_J_LOOP: for(int j=0; j<T; j+=2) {
                #pragma HLS pipeline II=1
                for(int tp=0; tp<TP; ++tp) {
                    __softmax_minus_t minus_0 = max_val[tp] - S_buf[tp][j]; 
                    __softmax_cursor1_t cur_0 = clamp((__softmax_cursor1_t)((minus_0 + b1) >> s1), (__softmax_cursor1_t)0, (__softmax_cursor1_t)bound1);
                    
                    __softmax_minus_t minus_1 = max_val[tp] - S_buf[tp][j+1]; 
                    __softmax_cursor1_t cur_1 = clamp((__softmax_cursor1_t)((minus_1 + b1) >> s1), (__softmax_cursor1_t)0, (__softmax_cursor1_t)bound1);
                    
                    acc_val[tp] += local_exp_table[cur_0] + local_exp_table[cur_1];
                }
            }

            // [Pass 2.5] 维持原来的倒数计算 (无需修改)
            __softmax_recip_t recip_val[TP];
            bool in_two[TP];
            #pragma HLS array_partition variable=recip_val complete
            #pragma HLS array_partition variable=in_two complete

            for(int tp=0; tp<TP; ++tp) {
                #pragma HLS unroll
                __softmax_cursor2_one_t cursor_one = (acc_val[tp] + b2_one) >> s2_one;
                if(cursor_one > bound2_one) {
                    in_two[tp] = 1;
                    __softmax_cursor2_two_t cursor_two = (acc_val[tp] + b2_two) >> s2_two;
                    cursor_two = clamp(cursor_two, 0, bound2_two);
                    recip_val[tp] = local_recip_table_two[cursor_two];
                } else {
                    in_two[tp] = 0;
                    cursor_one = clamp(cursor_one, 0, bound2_one);
                    recip_val[tp] = local_recip_table_one[cursor_one];
                }
            }

            long long O_acc[TP][CH];
            #pragma HLS array_partition variable=O_acc complete dim=0
            for(int tp=0; tp<TP; ++tp) {
                #pragma HLS unroll
                for(int c=0; c<CH; ++c) { 
                    #pragma HLS unroll
                    O_acc[tp][c] = 0;
                }
            }

            // ==========================================
            // [Pass 3]: 并行融合乘 V，彻底砍掉一半时间
            // ==========================================
            PASS3_J_LOOP: for(int j=0; j<T; j+=2) {
                #pragma HLS pipeline II=1
                for(int tp=0; tp<TP; ++tp) {
                    __softmax_minus_t minus_0 = max_val[tp] - S_buf[tp][j];
                    __softmax_cursor1_t cur_0 = clamp((__softmax_cursor1_t)((minus_0 + b1) >> s1), (__softmax_cursor1_t)0, (__softmax_cursor1_t)bound1);
                    __softmax_affine_t val_0 = local_exp_table[cur_0] * recip_val[tp];
                    
                    __softmax_minus_t minus_1 = max_val[tp] - S_buf[tp][j+1];
                    __softmax_cursor1_t cur_1 = clamp((__softmax_cursor1_t)((minus_1 + b1) >> s1), (__softmax_cursor1_t)0, (__softmax_cursor1_t)bound1);
                    __softmax_affine_t val_1 = local_exp_table[cur_1] * recip_val[tp];
                    
                    int rel_b3 = (in_two[tp] == 1) ? b3_two : b3_one;
                    int rel_s3 = (in_two[tp] == 1) ? s3_two : s3_one;
                    
                    int rq_val_0 = quantize_clamp((val_0 + rel_b3) >> rel_s3, clamp_bits, false);
                    int rq_val_1 = quantize_clamp((val_1 + rel_b3) >> rel_s3, clamp_bits, false);

                    for(int c=0; c<CH; ++c) {
                        #pragma HLS unroll
                        // 一周期吸入两个 V_buf 进行累加
                        O_acc[tp][c] += rq_val_0 * V_buf[j][c] + rq_val_1 * V_buf[j+1][c];
                    }
                }
            } 

            // ==========================================
            // 4. 写出结果给下游 (对齐 A 的数据流格式)
            // ==========================================
            WRITE_CT_LOOP: for(int ct=0; ct<CHT_OUT; ++ct) {
                #pragma HLS pipeline II=1
                hls::vector<__a_t, TP * AQ_CP> out_vec;
                for(int tp=0; tp<TP; ++tp) {
                    #pragma HLS unroll
                    for(int cp=0; cp<AQ_CP; ++cp) {
                        #pragma HLS unroll
                        int c_idx = ct * AQ_CP + cp;
                        out_vec[tp * AQ_CP + cp] = (__a_t)(O_acc[tp][c_idx]);
                    }
                }
                a_sm.write(out_vec);
            }
        } // end tt loop
    }
};

#endif 