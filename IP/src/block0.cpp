#include "common.h"
#include "attn.h"
#include "mlp.h"
#include "dataflow.h"
#include <string.h>
#include <ap_axi_sdata.h>

#include "patch_embed.h"
#include "head.h" 
#include "fixed_patch_head_rom.h"

using fixed_patch_head_rom::PATCH_WEIGHT_BANK;
using fixed_patch_head_rom::PATCH_BIAS_BANK;
using fixed_patch_head_rom::PATCH_CLS_BANK;

const int H         = 3;
const int TP        = 2;
const int CAP       = 1;
const int RESI_CP   = 2;
const int CHAP      = 4;
const int HEAD_COP  = 8;

const int MATMUL_QKV_CIP = 16;  const int MATMUL_QKV_COP = 16; 
const int Q_QKV_CP = 1;
// const int MATMUL_R_CIP   = 4;  const int MATMUL_R_COP   = 7;  const int RQ_CP      = 1;
// const int MATMUL_A_CIP   = 7;  const int MATMUL_A_COP   = 4;  const int AQ_CP      = 1;
// const int MATMUL_O_CIP   = 12; const int MATMUL_O_COP   = 6;
// const int MATMUL_QKV_CIP = 8;  const int MATMUL_QKV_COP = 8; 
// const int Q_QKV_CP = 1;
const int MATMUL_R_CIP   = 4;  const int MATMUL_R_COP   = 7;  const int RQ_CP      = 1;
const int MATMUL_A_CIP   = 7;  const int MATMUL_A_COP   = 4;  const int AQ_CP      = 1;
const int MATMUL_O_CIP   = 24; const int MATMUL_O_COP   = 12;

// const int M1_CIP = 12; const int M1_COP = 24;
// const int M2_CIP = 24; const int M2_COP = 12;
const int M1_CIP = 16; const int M1_COP = 32;
const int M2_CIP = 32; const int M2_COP = 16;

typedef ap_int<13> __attn_if_t;   typedef ap_int<15> __attn_of_t;
typedef ap_int<15> __mlp_if_t;    typedef ap_int<13> __mlp_of_t;

typedef hls::axis<hls::vector<ap_int<16>, TP*CAP>, 0, 0, 0> axis_in_pkt;
typedef hls::axis<hls::vector<ap_int<16>, TP*CAP>, 0, 0, 0> axis_out_pkt;

typedef ap_int<3> __attn_lnq_t;   typedef ap_int<3> __mlp_ln_t;
typedef ap_int<3> __attn_qq_t;    typedef ap_int<3> __attn_kq_t;
typedef ap_int<3> __attn_vq_t;    typedef ap_uint<3> __attn_rq_t;
typedef ap_int<3> __attn_aq_t;    typedef ap_uint<3> __mlp_ge_t;

typedef ap_int<3> __q_we_t;       typedef ap_int<3> __k_we_t;
typedef ap_int<3> __v_we_t;       typedef ap_int<3> __o_we_t;
typedef ap_int<3> __m1_we_t;      typedef ap_int<3> __m2_we_t;

typedef int __ln_sum_t;
typedef int __ln_divc_t;
typedef int __ln_mu_t;
typedef int __ln_rsqrt_t;
typedef int __ln_cursor_t;        typedef int __ln_shift_t;
typedef ap_int<40> __ln_affine_t;  
typedef ap_int<36> __ln_var_t;     

typedef ap_int   <  12 >   __attn_q_t;
typedef ap_int   <  11 >   __attn_k_t;
typedef ap_int   <  11 >   __attn_v_t;
typedef ap_int   <  10 >   __attn_r_t;
typedef ap_int   <  11 >   __attn_a_t;
typedef ap_int   <  13 >   __attn_o_t;

typedef __attn_q_t          __q_bi_t;
typedef __attn_v_t          __v_bi_t;
typedef __attn_k_t          __k_bi_t;
typedef __attn_o_t          __o_bi_t;

typedef ap_int   <  11 >   __mlp_m1_t;
typedef ap_int   <  13 >   __mlp_m2_t;

typedef ap_int   <  11 >   __m1_bi_t;
typedef ap_int   <  11 >   __m1_mc_t;

typedef ap_int   <  13 >   __m2_bi_t;
typedef ap_int   <  13 >   __m2_mc_t;

// qq, kq, vq, aq
typedef ap_int   <   9 >   __qq_cursor_t;
typedef ap_int   <   9 >   __kq_cursor_t;
typedef ap_int   <   9 >   __vq_cursor_t;
typedef ap_int   <  10 >   __aq_cursor_t;

typedef int __gelu_cursor_t;

// softmax
typedef ap_int   <  11 >   __softmax_minus_t;
typedef ap_uint  <   8 >   __softmax_cursor1_t;
typedef ap_uint  <  16 >   __softmax_exp_t;
typedef ap_uint  <  23 >   __softmax_acc_t;
typedef ap_uint  <   8 >   __softmax_recip_t;
typedef ap_uint  <   9 >   __softmax_cursor2_one_t;
typedef ap_int   <   7 >   __softmax_cursor2_two_t;
typedef ap_uint  <  23 >   __softmax_affine_t;
typedef ap_uint  <   8 >   __softmax_cursor3_t;

// --- 实例化预处理与骨干网 ---
typedef PatchEmbed<
    ap_int<16>, int, int, int, ap_int<13>,
    T, TP, 768, 24, 1, C, 12, CAP, true
> PatchEmbedCoreType;
static PatchEmbedCoreType patch_inst;

#define TT (T/TP)
#define CAT (C/CAP)

typedef Attn<
    H, T, TP, C, CAP, RESI_CP, MATMUL_QKV_CIP, MATMUL_QKV_COP, Q_QKV_CP, MATMUL_R_CIP, MATMUL_R_COP, RQ_CP, MATMUL_A_CIP, MATMUL_A_COP, AQ_CP,
    MATMUL_O_CIP, MATMUL_O_COP, __attn_if_t, __attn_lnq_t, __attn_q_t, __attn_k_t, __attn_v_t, __attn_r_t, __attn_a_t, __attn_o_t, __attn_qq_t,
    __attn_kq_t, __attn_vq_t, __attn_rq_t, __attn_aq_t, __attn_of_t, __ln_sum_t, __ln_divc_t, __ln_mu_t, __ln_var_t, __ln_cursor_t, __ln_rsqrt_t,
    __ln_affine_t, __ln_shift_t, 128, __q_we_t, __q_bi_t, 32, 2, 0, 2, LRAM_STYLE, false, __k_we_t, __k_bi_t, 32, 2, 0, 2, LRAM_STYLE, false,
    __v_we_t, __v_bi_t, 32, 2, 0, 2, LRAM_STYLE, false, __qq_cursor_t, 64, __kq_cursor_t, 64, __vq_cursor_t, 64, __aq_cursor_t, 64, 32, 2, 2, 2, LRAM_STYLE, false,
    __softmax_minus_t, __softmax_cursor1_t, __softmax_exp_t, __softmax_acc_t, __softmax_recip_t, __softmax_cursor2_one_t, __softmax_cursor2_two_t,
    __softmax_affine_t, __softmax_cursor3_t, 32, 64, 32, 2, 2, 2, LRAM_STYLE, false, __o_we_t, __o_bi_t, 32, 2, 0, 2, LRAM_STYLE, false, 2, 512, 12288, 512, 2, 2, 2, 2, 2, 2, 2, 2, 8000, 64, 64, 512, 512, 512, 512, 64, 2, 2, 2
> AttnCoreType;

typedef MLP<
    T, TP, C, CAP, RESI_CP, MLP_CH, CHAP, __mlp_if_t, __mlp_ln_t, __mlp_m1_t, __mlp_ge_t, __mlp_m2_t, __mlp_of_t,
    __ln_sum_t, __ln_divc_t, __ln_mu_t, __ln_var_t, __ln_cursor_t, __ln_rsqrt_t, __ln_affine_t, __ln_shift_t, 128,
    __m1_we_t, __m1_bi_t, __m1_mc_t, M1_CIP, M1_COP, 32, 2, 0, 2, false,
    __gelu_cursor_t, 64, __m2_we_t, __m2_bi_t, __m2_mc_t, M2_CIP, M2_COP, 32, 2, 0, 2, false
> MlpCoreType;

typedef hls::vector<ap_int<16>, TP*CAP> fm_vec_t;

// --- 🚨 实例化 Head 硬件模块 ---
typedef ap_int<8>   __head_ln_t;    typedef ap_int<8>   __head_we_t;
typedef ap_int<19>  __head_bi_t;    typedef ap_int<19>  __head_mc_t;
typedef ap_uint<15> __head_ln_sum_t;typedef ap_uint<30> __head_ln_divc_t;
typedef ap_uint<7>  __head_ln_mu_t; typedef ap_uint<24> __head_ln_var_t;
typedef ap_uint<6>  __head_ln_cursor_t; typedef ap_uint<11> __head_ln_rsqrt_t;
typedef ap_int<36>  __head_ln_affine_t; typedef ap_int<9>   __head_ln_shift_t;

typedef Head<
    T, TP, C, 1, 1000, 1,
    __attn_if_t, __head_ln_t, __head_we_t, __head_bi_t, __head_mc_t,
    __head_ln_sum_t, __head_ln_divc_t, __head_ln_mu_t, __head_ln_var_t,
    __head_ln_cursor_t, __head_ln_rsqrt_t, __head_ln_affine_t, __head_ln_shift_t,
    128, 1, 4, 2, 2, 2, 2, false
> HeadCoreType;

static HeadCoreType head_inst;

static void load_fixed_patch_from_rom() {
    #pragma HLS inline off
    patch_inst.s = fixed_patch_head_rom::PATCH_SCALARS[0];
    patch_inst.b = (patch_inst.s > 0) ? (1 << (patch_inst.s - 1)) : 0;

    for (int co = 0; co < C; co++) {
        for (int ci = 0; ci < CI; ci++) {
            #pragma HLS pipeline II=1
            patch_inst.weight_arr[co][ci] = fixed_patch_head_rom::PATCH_WEIGHT[co][ci];
        }
    }

    for (int t = 0; t < T; t++) {
        for (int co = 0; co < C; co++) {
            #pragma HLS pipeline II=1
            patch_inst.bias_arr[t][co] = fixed_patch_head_rom::PATCH_BIAS[t * C + co];
        }
    }

    for (int co = 0; co < C; co++) {
        #pragma HLS pipeline II=1
        patch_inst.cls_arr[co] = fixed_patch_head_rom::PATCH_CLS[co];
    }
}

static void load_fixed_head_from_rom() {
    #pragma HLS inline off
    for (int i = 0; i < 7; i++) {
        #pragma HLS pipeline II=1
        head_inst.lnq.local_scalars[i] = fixed_patch_head_rom::HEAD_LN_SCALARS[i];
    }

    for (int i = 0; i < C; i++) {
        #pragma HLS pipeline II=1
        head_inst.lnq.local_lnw_ram[i] = fixed_patch_head_rom::HEAD_LNW[i];
    }

    for (int i = 0; i < C; i++) {
        #pragma HLS pipeline II=1
        head_inst.lnq.local_lnb_ram[i] = fixed_patch_head_rom::HEAD_LNB[i];
    }

    for (int i = 0; i < 128; i++) {
        #pragma HLS pipeline II=1
        head_inst.lnq.local_rsqrt_table[i] = fixed_patch_head_rom::HEAD_RSQRT[i];
    }

    for (int co = 0; co < 1000; co++) {
        #pragma HLS pipeline II=1
        head_inst.matmul.local_bias_ram[co] = fixed_patch_head_rom::HEAD_BIAS[co];
    }

    for (int co = 0; co < 1000; co++) {
        for (int ci = 0; ci < C; ci++) {
            #pragma HLS pipeline II=1
            head_inst.matmul.local_weight_ram[co][ci] = fixed_patch_head_rom::HEAD_WEIGHT[co][ci];
        }
    }
}

static void ensure_fixed_patch_head_loaded() {
    #pragma HLS inline off
    static bool loaded = false;
    if (!loaded) {
        load_fixed_patch_from_rom();
        load_fixed_head_from_rom();
        loaded = true;
    }
}

static void fixed_patch_step2_mac_replace_shift(
    hls::stream<hls::vector<ap_int<16>, TP*24> >& i_stream,
    hls::stream<hls::vector<ap_int<13>, TP*12> >& o_stream
) {
    #pragma HLS inline off
    #pragma HLS array_partition variable=PATCH_WEIGHT_BANK complete dim=1
    #pragma HLS array_partition variable=PATCH_WEIGHT_BANK complete dim=2
    #pragma HLS array_partition variable=PATCH_BIAS_BANK complete dim=1
    #pragma HLS array_partition variable=PATCH_BIAS_BANK complete dim=2
    #pragma HLS array_partition variable=PATCH_CLS_BANK complete dim=1

    const int s = fixed_patch_head_rom::PATCH_SCALARS[0];
    const int b = (s > 0) ? (1 << (s - 1)) : 0;

    int acc_buf[C / 12][TP][12];
    #pragma HLS array_partition variable=acc_buf complete dim=2
    #pragma HLS array_partition variable=acc_buf complete dim=3

    TT_LOOP: for (int tt = 0; tt < TT; ++tt) {
        CIT_LOOP: for (int cit = 0; cit < CI / 24; ++cit) {
            hls::vector<ap_int<16>, TP*24> vec_i = i_stream.read();

            COT_LOOP: for (int cot = 0; cot < C / 12; ++cot) {
                #pragma HLS pipeline II=1

                for (int tp = 0; tp < TP; ++tp) {
                    #pragma HLS unroll factor=2
                    for (int cop = 0; cop < 12; ++cop) {
                        #pragma HLS unroll factor=2

                        int sum = 0;
                        for (int cip = 0; cip < 24; ++cip) {
                            #pragma HLS unroll
                            auto a_val = vec_i[tp * 24 + cip];
                            auto w_val = PATCH_WEIGHT_BANK[cop][cip][cot][cit];
                            auto mul_res = a_val * w_val;
                            #pragma HLS bind_op variable=mul_res op=mul impl=dsp
                            sum += mul_res;
                        }

                        if (cit == 0) {
                            int init_val = 0;
                            if (!(tt == 0 && tp == 0)) {
                                init_val = PATCH_BIAS_BANK[tp][cop][tt][cot];
                            }
                            acc_buf[cot][tp][cop] = init_val + sum;
                        } else {
                            acc_buf[cot][tp][cop] += sum;
                        }
                    }
                }
            }
        }

        WRITE_COT_LOOP: for (int cot = 0; cot < C / 12; ++cot) {
            #pragma HLS pipeline II=1
            hls::vector<ap_int<13>, TP*12> vec_o_shift;

            for (int tp = 0; tp < TP; ++tp) {
                #pragma HLS unroll
                for (int cop = 0; cop < 12; ++cop) {
                    #pragma HLS unroll
                    int final_val = acc_buf[cot][tp][cop];
                    if (tt == 0 && tp == 0) {
                        final_val = PATCH_CLS_BANK[cop][cot];
                    }
                    vec_o_shift[tp * 12 + cop] = (final_val + b) >> s;
                }
            }
            o_stream.write(vec_o_shift);
        }
    }
}

static void fixed_patch_do_patch_embed(
    hls::stream<hls::vector<ap_int<16>, TP*CAP> >& i_stream,
    hls::stream<hls::vector<ap_int<13>, TP*CAP> >& o_stream
) {
    #pragma HLS dataflow

    Adapter<ap_int<16>, T, TP, CI, CAP, 24> adapter_i;
    Adapter<ap_int<13>, T, TP, C, 12, CAP> adapter_o;

    hls::stream<hls::vector<ap_int<16>, TP*24> > adpt_sm("fixed_patch_adpt_sm");
    hls::stream<hls::vector<ap_int<13>, TP*12> > mac_sm("fixed_patch_mac_sm");
    #pragma HLS stream variable=adpt_sm depth=64
    #pragma HLS stream variable=mac_sm depth=2

    adapter_i.do_adapt(i_stream, adpt_sm);
    fixed_patch_step2_mac_replace_shift(adpt_sm, mac_sm);
    adapter_o.do_adapt(mac_sm, o_stream);
}

static void fixed_head_select_cls(
    hls::stream<hls::vector<__attn_if_t, TP*CAP> >& i_stream,
    hls::stream<hls::vector<__attn_if_t, CAP> >& o_stream
) {
    #pragma HLS inline off

    TT_LOOP: for (int tt = 0; tt < TT; ++tt) {
        CIAT_LOOP: for (int ciat = 0; ciat < CAT; ++ciat) {
            #pragma HLS pipeline II=1
            hls::vector<__attn_if_t, TP*CAP> vec_i = i_stream.read();
            if (tt == 0) {
                hls::vector<__attn_if_t, CAP> vec_o;
                for (int ciap = 0; ciap < CAP; ++ciap) {
                    #pragma HLS unroll
                    vec_o[ciap] = vec_i[ciap];
                }
                o_stream.write(vec_o);
            }
        }
    }
}

static void fixed_head_layernorm(
    hls::stream<hls::vector<__attn_if_t, CAP> >& i_stream,
    hls::stream<hls::vector<__head_ln_t, CAP> >& o_stream
) {
    #pragma HLS inline off

    const int C_1_m = fixed_patch_head_rom::HEAD_LN_SCALARS[0];
    const int C_1_s = fixed_patch_head_rom::HEAD_LN_SCALARS[1];
    const int b = fixed_patch_head_rom::HEAD_LN_SCALARS[2];
    const int s1 = fixed_patch_head_rom::HEAD_LN_SCALARS[3];
    const int bound = fixed_patch_head_rom::HEAD_LN_SCALARS[4];
    const int s2 = fixed_patch_head_rom::HEAD_LN_SCALARS[5];
    const int clamp_bits = fixed_patch_head_rom::HEAD_LN_SCALARS[6];

    __attn_if_t buffer[C];
    #pragma HLS bind_storage variable=buffer type=ram_2p impl=bram

    __head_ln_mu_t mean = 0;
    __head_ln_rsqrt_t st_sqrt = 0;
    __head_ln_sum_t acc = 0;
    __head_ln_var_t sum = 0;

    STATE_LOOP: for (int state = 0; state < 3; ++state) {
        CT_LOOP: for (int ct = 0; ct < C; ++ct) {
            #pragma HLS pipeline II=1

            if (state == 0) {
                hls::vector<__attn_if_t, CAP> vec_i = i_stream.read();
                if (ct == 0) {
                    acc = 0;
                }
                buffer[ct] = vec_i[0];
                acc += vec_i[0];

                if (ct == C - 1) {
                    __head_ln_divc_t tmp = acc * C_1_m;
                    tmp += (1 << (C_1_s - 1));
                    mean = tmp >> C_1_s;
                }
            } else if (state == 1) {
                __attn_if_t diff = buffer[ct] - mean;
                auto diff_pow2 = diff * diff;
                sum = (ct == 0) ? __head_ln_var_t(diff_pow2) : __head_ln_var_t(sum + diff_pow2);

                if (ct == C - 1) {
                    __head_ln_cursor_t cursor = (sum + b) >> s1;
                    cursor = clamp(cursor, 0, bound);
                    st_sqrt = fixed_patch_head_rom::HEAD_RSQRT[cursor];
                }
            } else {
                hls::vector<__head_ln_t, CAP> o_vec;
                __attn_if_t diff = buffer[ct] - mean;
                __head_ln_affine_t val =
                    diff * st_sqrt * fixed_patch_head_rom::HEAD_LNW[ct] +
                    fixed_patch_head_rom::HEAD_LNB[ct];
                __head_ln_shift_t rel = val >> s2;
                o_vec[0] = quantize_clamp(rel, clamp_bits, true);
                o_stream.write(o_vec);
            }
        }
    }
}

static void fixed_head_matmul_core(
    hls::stream<hls::vector<__head_ln_t, CAP> >& i_stream,
    hls::stream<hls::vector<__head_mc_t, HEAD_COP> >& o_stream
) {
    #pragma HLS inline off

    __head_ln_t wb[C];
    #pragma HLS bind_storage variable=wb type=ram_1p impl=bram

    READ_LOOP: for (int ci = 0; ci < C; ++ci) {
        #pragma HLS pipeline II=1
        wb[ci] = i_stream.read()[0];
    }

    COT_LOOP: for (int cot = 0; cot < 1000 / HEAD_COP; ++cot) {
        hls::vector<__head_mc_t, HEAD_COP> vec_o;

        CIT_LOOP: for (int cit = 0; cit < C; ++cit) {
            #pragma HLS pipeline II=1

            if (cit == 0) {
                for (int cop = 0; cop < HEAD_COP; ++cop) {
                    #pragma HLS unroll
                    vec_o[cop] = fixed_patch_head_rom::HEAD_BIAS[cot * HEAD_COP + cop];
                }
            }

            for (int cop = 0; cop < HEAD_COP; ++cop) {
                #pragma HLS unroll
                auto mul_res = wb[cit] * fixed_patch_head_rom::HEAD_WEIGHT[cot * HEAD_COP + cop][cit];
                #pragma HLS bind_op variable=mul_res op=mul impl=dsp latency=2
                vec_o[cop] += mul_res;
            }

            if (cit == C - 1) {
                o_stream.write(vec_o);
            }
        }
    }
}

static void fixed_head_matmul(
    hls::stream<hls::vector<__head_ln_t, CAP> >& i_stream,
    hls::stream<hls::vector<__head_mc_t, 1> >& o_stream
) {
    #pragma HLS dataflow

    Adapter<__head_mc_t, 1, 1, 1000, HEAD_COP, 1> adapter_o;
    hls::stream<hls::vector<__head_mc_t, HEAD_COP> > mac_sm("fixed_head_mac_sm");
    #pragma HLS stream variable=mac_sm depth=2

    fixed_head_matmul_core(i_stream, mac_sm);
    adapter_o.do_adapt(mac_sm, o_stream);
}

static void fixed_head_do_head(
    hls::stream<hls::vector<__attn_if_t, CAP> >& i_stream,
    hls::stream<hls::vector<__head_mc_t, 1> >& o_stream
) {
    #pragma HLS dataflow

    hls::stream<hls::vector<__head_ln_t, CAP> > ln_sm("fixed_head_ln_sm");
    #pragma HLS stream variable=ln_sm depth=2

    fixed_head_layernorm(i_stream, ln_sm);
    fixed_head_matmul(ln_sm, o_stream);
}

// ==========================================
// 🚀 终极内存对齐修复方案：显式状态机复制，杜绝 memcpy 造成的突发错位
// ==========================================
template<typename T_VAL>
void copy_arr(T_VAL* dst, const T_VAL* src, int len) {
    #pragma HLS inline
    for(int i = 0; i < len; i++) {
        #pragma HLS pipeline II=1
        dst[i] = src[i];
    }
}

// 🚀 传入单一的指针 load_weights，并将边界检查放入内部，使得外部可以无条件调用
void task_load_weights(const BlockLayerWeights* ext_weights, int layer_idx, int num_layers, BlockLayerWeights* local_bram) {
    #pragma HLS inline off
    
    // 🚨 如果超出层数则直接返回（相当于产生一个周期的空操作，维持了 Dataflow 拓扑完整性）
    if (layer_idx >= num_layers) return; 

    const AttnLayerWeights& ext_attn = ext_weights[layer_idx].attn_weights;
    AttnLayerWeights& loc_attn = local_bram->attn_weights;

    // --- Attn 权重 ---
    copy_arr(loc_attn.q_weight, ext_attn.q_weight, 1152);
    copy_arr(loc_attn.k_weight, ext_attn.k_weight, 1152);
    copy_arr(loc_attn.v_weight, ext_attn.v_weight, 1152);
    copy_arr(loc_attn.q_bias,   ext_attn.q_bias,   24);
    copy_arr(loc_attn.k_bias,   ext_attn.k_bias,   24);
    copy_arr(loc_attn.v_bias,   ext_attn.v_bias,   24);
    copy_arr(loc_attn.o_weight, ext_attn.o_weight, 1152);
    copy_arr(loc_attn.o_bias,   ext_attn.o_bias,   24);

    // --- Attn 标量 ---
    copy_arr(loc_attn.attn_scalars,   ext_attn.attn_scalars,   3);
    copy_arr(loc_attn.ln_scalars,     ext_attn.ln_scalars,     7);
    copy_arr(loc_attn.ln_lnw,         ext_attn.ln_lnw,         C);
    copy_arr(loc_attn.ln_lnb,         ext_attn.ln_lnb,         C);
    copy_arr(loc_attn.ln_rsqrt_table, ext_attn.ln_rsqrt_table, 128);

    copy_arr(loc_attn.qq_scalars, ext_attn.qq_scalars, 4);
    copy_arr(loc_attn.kq_scalars, ext_attn.kq_scalars, 4);
    copy_arr(loc_attn.vq_scalars, ext_attn.vq_scalars, 4);
    copy_arr(loc_attn.aq_scalars, ext_attn.aq_scalars, 4);

    copy_arr(loc_attn.qq_table, ext_attn.qq_table, 64);
    copy_arr(loc_attn.kq_table, ext_attn.kq_table, 64);
    copy_arr(loc_attn.vq_table, ext_attn.vq_table, 64);
    copy_arr(loc_attn.aq_table, ext_attn.aq_table, 64);

    copy_arr(loc_attn.softmax_scalars,         ext_attn.softmax_scalars,         14);
    copy_arr(loc_attn.softmax_exp_table,       ext_attn.softmax_exp_table,       32);
    copy_arr(loc_attn.softmax_recip_table_one, ext_attn.softmax_recip_table_one, 64);
    copy_arr(loc_attn.softmax_recip_table_two, ext_attn.softmax_recip_table_two, 64);

    // --- MLP 权重 ---
    const MlpLayerWeights& ext_mlp = ext_weights[layer_idx].mlp_weights;
    MlpLayerWeights& loc_mlp = local_bram->mlp_weights;

    copy_arr(loc_mlp.m1_weight, ext_mlp.m1_weight, 4608);
    copy_arr(loc_mlp.m1_bias,   ext_mlp.m1_bias,   96);
    copy_arr(loc_mlp.m2_weight, ext_mlp.m2_weight, 4608);
    copy_arr(loc_mlp.m2_bias,   ext_mlp.m2_bias,   24);

    // --- MLP 标量 ---
    copy_arr(loc_mlp.mlp_scalars,    ext_mlp.mlp_scalars,    2);
    copy_arr(loc_mlp.ln_scalars,     ext_mlp.ln_scalars,     7);
    copy_arr(loc_mlp.ln_lnw,         ext_mlp.ln_lnw,         C);
    copy_arr(loc_mlp.ln_lnb,         ext_mlp.ln_lnb,         C);
    copy_arr(loc_mlp.ln_rsqrt_table, ext_mlp.ln_rsqrt_table, 128);
    copy_arr(loc_mlp.ge_scalars,     ext_mlp.ge_scalars,     4);
    copy_arr(loc_mlp.ge_table,       ext_mlp.ge_table,       64);
}


void task_read_fm_resi(fm_vec_t fm_bram[TT*CAT], hls::stream<hls::vector<__attn_if_t, TP*CAP> >& stream_resi) {
    #pragma HLS inline off
    for(int i=0; i<TT*CAT; i++) {
        #pragma HLS pipeline II=1
        fm_vec_t raw = fm_bram[i];
        hls::vector<__attn_if_t, TP*CAP> vec;
        for(int j=0; j<TP*CAP; j++) vec[j] = raw[j];
        stream_resi.write(vec);
    }
}

void task_compute_attn(
    hls::stream<hls::vector<__attn_if_t, TP*CAP> >& i_stream_main,
    hls::stream<hls::vector<__attn_if_t, TP*CAP> >& i_stream_resi,
    hls::stream<hls::vector<__attn_of_t, TP*CAP> >& o_stream,
    const BlockLayerWeights* local_bram
) {
    #pragma HLS inline off
#ifndef __SYNTHESIS__
    AttnCoreType* attn_inst = new AttnCoreType();
    attn_inst->load_weights_from_bram(&local_bram->attn_weights);
    attn_inst->do_attn(i_stream_main, i_stream_resi, o_stream);
    delete attn_inst;
#else
    static AttnCoreType attn_inst;
    attn_inst.load_weights_from_bram(&local_bram->attn_weights);
    attn_inst.do_attn(i_stream_main, i_stream_resi, o_stream);
#endif
}

static void task_stream_cast(
    hls::stream<hls::vector<__attn_of_t, TP*CAP> >& in,
    hls::stream<hls::vector<__mlp_if_t, TP*CAP> >& out
) {
    #pragma HLS inline off
    for(int i = 0; i < TT * CAT; i++) {
        #pragma HLS pipeline II=1
        hls::vector<__attn_of_t, TP*CAP> vec_in = in.read();
        hls::vector<__mlp_if_t, TP*CAP> vec_out;
        for(int j = 0; j < TP*CAP; j++) vec_out[j] = vec_in[j];
        out.write(vec_out);
    }
}

void task_compute_mlp(
    hls::stream<hls::vector<__mlp_if_t, TP*CAP> >& i_stream,
    hls::stream<hls::vector<__mlp_of_t,  TP*CAP> >& o_stream,
    const BlockLayerWeights* local_bram
) {
    #pragma HLS inline off
#ifndef __SYNTHESIS__
    MlpCoreType* mlp_inst = new MlpCoreType();
    mlp_inst->load_weights_from_bram(&local_bram->mlp_weights);
    mlp_inst->do_mlp(i_stream, o_stream);
    delete mlp_inst;
#else
    static MlpCoreType mlp_inst;
    mlp_inst.load_weights_from_bram(&local_bram->mlp_weights);
    mlp_inst.do_mlp(i_stream, o_stream);
#endif
}

// ==========================================
// AXI 外部数据搬运与内部格式转换
// ==========================================
void task_recv_img(hls::stream<axis_in_pkt>& ext_stream, hls::stream<hls::vector<ap_int<16>, TP*CAP>>& img_stream) {
    #pragma HLS inline off
    for(int i = 0; i < T * 768 / (TP * CAP); i++) {
        #pragma HLS pipeline II=1
        axis_in_pkt pkt = ext_stream.read();
        img_stream.write(pkt.data);
    }
}

void task_write_pe_to_fm(hls::stream<hls::vector<ap_int<13>, TP*CAP>>& pe_out, fm_vec_t fm_bram[TT*CAT]) {
    #pragma HLS inline off
    for(int i = 0; i < TT * CAT; i++) {
        #pragma HLS pipeline II=1
        hls::vector<ap_int<13>, TP*CAP> vec = pe_out.read();
        fm_vec_t raw;
        for(int j=0; j<TP*CAP; j++) raw[j] = vec[j];
        fm_bram[i] = raw; 
    }
}

void task_read_fm(fm_vec_t fm_bram[TT*CAT], hls::stream<hls::vector<__attn_if_t, TP*CAP> >& stream_out) {
    #pragma HLS inline off
    for(int i=0; i<TT*CAT; i++) {
        #pragma HLS pipeline II=1
        fm_vec_t raw = fm_bram[i];
        hls::vector<__attn_if_t, TP*CAP> vec;
        for(int j=0; j<TP*CAP; j++) vec[j] = raw[j];
        stream_out.write(vec);
    }
}

void task_read_cls_fm(fm_vec_t fm_bram[TT*CAT], hls::stream<hls::vector<__attn_if_t, CAP> >& stream_out) {
    #pragma HLS inline off
    for(int ciat=0; ciat<CAT; ciat++) {
        #pragma HLS pipeline II=1
        fm_vec_t raw = fm_bram[ciat];
        hls::vector<__attn_if_t, CAP> vec;
        for(int cap=0; cap<CAP; cap++) {
            #pragma HLS unroll
            vec[cap] = raw[cap];
        }
        stream_out.write(vec);
    }
}

void task_write_fm(hls::stream<hls::vector<__mlp_of_t, TP*CAP> >& stream_in, fm_vec_t fm_bram[TT*CAT]) {
    #pragma HLS inline off
    for(int i=0; i<TT*CAT; i++) {
        #pragma HLS pipeline II=1
        hls::vector<__mlp_of_t, TP*CAP> vec = stream_in.read();
        fm_vec_t raw;
        for(int j=0; j<TP*CAP; j++) raw[j] = vec[j];
        fm_bram[i] = raw;
    }
}

void task_read_fm_split(
    fm_vec_t fm_bram[TT*CAT],
    hls::stream<hls::vector<__attn_if_t, TP*CAP> >& stream_main,
    hls::stream<hls::vector<__attn_if_t, TP*CAP> >& stream_resi
) {
    #pragma HLS inline off
    for(int i=0; i<TT*CAT; i++) {
        #pragma HLS pipeline II=1
        fm_vec_t raw = fm_bram[i];
        hls::vector<__attn_if_t, TP*CAP> vec;
        for(int j=0; j<TP*CAP; j++) vec[j] = raw[j];
        
        stream_main.write(vec);
        stream_resi.write(vec);
    }
}

void task_run_pe(hls::stream<axis_in_pkt>& i_stream_ext, fm_vec_t fm_bram_0[TT * CAT]) {
    #pragma HLS dataflow
    hls::stream<hls::vector<ap_int<16>, TP*CAP> > img_sm("img_sm");
    hls::stream<hls::vector<ap_int<13>, TP*CAP> > pe_out_sm("pe_out_sm");
    task_recv_img(i_stream_ext, img_sm);
    fixed_patch_do_patch_embed(img_sm, pe_out_sm);
    task_write_pe_to_fm(pe_out_sm, fm_bram_0);
}

void task_write_logits(hls::stream<hls::vector<__head_mc_t, 1> >& head_out_sm, hls::stream<hls::axis<int, 0,0,0>>& o_logits) {
    #pragma HLS inline off
    for(int i = 0; i < 1000; i++) {
        #pragma HLS pipeline II=1
        hls::axis<int, 0,0,0> pkt;
        int val = (int)(head_out_sm.read()[0]); 
        pkt.data = val;
        pkt.keep = -1; pkt.strb = -1;
        pkt.last = (i == 999) ? 1 : 0;
        o_logits.write(pkt);
    }
}

void task_run_head(fm_vec_t fm_bram[TT * CAT], hls::stream<hls::axis<int, 0,0,0>>& o_logits) {
    #pragma HLS dataflow
    hls::stream<hls::vector<__attn_if_t, CAP> > head_in_sm("head_in_sm");
    hls::stream<hls::vector<__head_mc_t, 1> > head_out_sm("head_out_sm");
    
    #pragma HLS stream variable=head_in_sm depth=16
    #pragma HLS stream variable=head_out_sm depth=16

    task_read_cls_fm(fm_bram, head_in_sm);
    fixed_head_do_head(head_in_sm, head_out_sm);
    task_write_logits(head_out_sm, o_logits); 
}

void initial_overlap_wrapper(
    hls::stream<axis_in_pkt>& i_stream_ext,
    fm_vec_t fm_bram_0[TT * CAT],
    const BlockLayerWeights* ext_weights,
    BlockLayerWeights* load_weights
) {
    #pragma HLS dataflow
    task_run_pe(i_stream_ext, fm_bram_0);
    // 传入 num_layers=1，确保一定会执行
    task_load_weights(ext_weights, 0, 1, load_weights); 
}

void dataflow_wrapper(
    const BlockLayerWeights* ext_weights, int curr_layer, int num_layers,
    fm_vec_t* fm_src, fm_vec_t* fm_dst,
    const BlockLayerWeights* calc_weights, // 🚀 纯读指针 (const)
    BlockLayerWeights* load_weights        // 🚀 纯写指针
) {
    #pragma HLS dataflow
    hls::stream<hls::vector<__attn_if_t, TP*CAP> > i_stream_main("i_stream_main");
    hls::stream<hls::vector<__attn_if_t, TP*CAP> > i_stream_resi("i_stream_resi");
    hls::stream<hls::vector<__attn_of_t, TP*CAP> > mid_stream_int("mid_stream_int");
    hls::stream<hls::vector<__mlp_if_t,  TP*CAP> > mlp_in_stream("mlp_in_stream");
    hls::stream<hls::vector<__mlp_of_t,  TP*CAP> > o_stream_int("o_stream_int");

    #pragma HLS stream variable=i_stream_main depth=32
    #pragma HLS stream variable=i_stream_resi depth=19000
    #pragma HLS bind_storage variable=i_stream_resi type=fifo impl=bram
    #pragma HLS stream variable=mid_stream_int depth=32
    #pragma HLS stream variable=mlp_in_stream depth=32
    #pragma HLS stream variable=o_stream_int depth=32

    task_read_fm_split(fm_src, i_stream_main, i_stream_resi);

    // 对于计算侧，纯读取 calc_weights
    task_compute_attn(i_stream_main, i_stream_resi, mid_stream_int, calc_weights);
    task_stream_cast(mid_stream_int, mlp_in_stream);
    task_compute_mlp(mlp_in_stream, o_stream_int, calc_weights);
    task_write_fm(o_stream_int, fm_dst);

    task_load_weights(ext_weights, curr_layer + 1, num_layers, load_weights);
}

void vit_block_top(
    const BlockLayerWeights* ext_weights,
    hls::stream<axis_in_pkt>& i_stream_ext,
    hls::stream<hls::axis<int, 0,0,0>>& o_stream_logits,
    int num_layers
){
    #pragma HLS interface m_axi port=ext_weights   depth=12 offset=slave bundle=gmem_w max_read_burst_length=256 max_widen_bitwidth=128
    #pragma HLS interface axis port=i_stream_ext
    #pragma HLS interface axis port=o_stream_logits
    #pragma HLS interface s_axilite port=num_layers bundle=control
    #pragma HLS interface s_axilite port=return bundle=control

    static BlockLayerWeights pp_bram[2];
    #pragma HLS array_partition variable=pp_bram complete dim=1

    static fm_vec_t fm_bram[2][TT * CAT];
    #pragma HLS array_partition variable=fm_bram complete dim=1
    #pragma HLS bind_storage variable=fm_bram type=ram_2p impl=bram

   if (num_layers > 0) {
        // 🚀 传递对应 BRAM 的地址
        initial_overlap_wrapper(i_stream_ext, fm_bram[0], ext_weights, &pp_bram[0]);
    }

layer_loop: for(int l = 0; l < num_layers; l++) {
        // 🚀 终极杀招：用静态 if-else 彻底切断 HLS 的动态指针 MUX 推断！
        // 这样硬件会直接生成两条写死的物理连线，切层时绝对零延迟，绝不串线！
        if (l % 2 == 0) {
            // 偶数层：计算读 pp_bram[0]，加载写 pp_bram[1]
            dataflow_wrapper(
                ext_weights, l, num_layers,
                fm_bram[0], fm_bram[1],
                &pp_bram[0], &pp_bram[1] 
            );
        } else {
            // 奇数层：计算读 pp_bram[1]，加载写 pp_bram[0]
            dataflow_wrapper(
                ext_weights, l, num_layers,
                fm_bram[1], fm_bram[0],
                &pp_bram[1], &pp_bram[0] 
            );
        }
    }

if (num_layers > 0) {
        // 🚀 终极杀招延续：用静态分支决定分类头连向哪块 BRAM
        if (num_layers % 2 == 0) {
            // 偶数层跑完，最终输出一定在 fm_bram[0]
            task_run_head(fm_bram[0], o_stream_logits); 
        } else {
            // 奇数层跑完，最终输出一定在 fm_bram[1]
            task_run_head(fm_bram[1], o_stream_logits); 
        }
    }
}

// ==========================================
// Testbench (C-Simulation 纯硬件 1000 分类验证)
// ==========================================
#ifndef __SYNTHESIS__

#include <stdio.h>
#include <stdlib.h>

#include "../tests/multi_call.inc"

int e04_legacy_main(){
    printf("\n=======================================\n");
    printf("   ViT simulation (1000%% 纯硬件)\n");
    printf("=======================================\n");

    printf(" [结构体内存大小诊断]\n");
    printf("  -> sizeof(AttnLayerWeights) = %lu bytes\n", sizeof(AttnLayerWeights));
    printf("  -> sizeof(MlpLayerWeights)  = %lu bytes\n", sizeof(MlpLayerWeights));
    printf("  -> sizeof(BlockLayerWeights)= %lu bytes\n", sizeof(BlockLayerWeights));
    printf("  -> sizeof(PatchEmbedWeights)= %lu bytes\n", sizeof(PatchEmbedWeights));
    printf("  -> sizeof(HeadWeights)      = %lu bytes\n", sizeof(HeadWeights));
    printf("---------------------------------------\n");

    const int NUM_LAYERS = 12;

    BlockLayerWeights* mock_ddr_weights = new BlockLayerWeights[NUM_LAYERS]();
    int* input_data = new int[T * 768]();
    int* ref_logits = new int[1000](); 

    FILE* fw = fopen("weights.bin", "rb");
    if(!fw) { printf("❌ 致命错误: 找不到 weights.bin\n"); return -1; }
    fread(mock_ddr_weights, sizeof(BlockLayerWeights), NUM_LAYERS, fw);
    fclose(fw);

    FILE* fin = fopen("input.bin", "rb");
    if(!fin) { printf("❌ 致命错误: 找不到 input.bin\n"); return -1; }
    fread(input_data, sizeof(int), T * 768, fin);
    fclose(fin);

    FILE* fout = fopen("output.bin", "rb");
    if(!fout) { printf("❌ 致命错误: 找不到 output.bin\n"); return -1; }
    fread(ref_logits, sizeof(int), 1000, fout);
    fclose(fout);

    printf("📦 所有二进制权重与图片数据加载完毕！\n");

    hls::stream<axis_in_pkt> i_stream("i_stream");
    hls::stream<hls::axis<int, 0,0,0>> o_stream_logits("o_stream_logits");

    const int CI = 768;
    for(int tt = 0; tt < T / TP; tt++) {
        for(int c = 0; c < CI; c++) {
            hls::vector<ap_int<16>, TP*CAP> vec_i;
            for(int tp = 0; tp < TP; tp++) {
                int t_idx = tt * TP + tp;
                vec_i[tp] = (ap_int<16>)input_data[t_idx * CI + c];
            }
            axis_in_pkt pkt; pkt.data = vec_i; pkt.keep = -1; pkt.strb = -1; pkt.last = 0;
            i_stream.write(pkt);
        }
    }

    printf("🚀 启动 1000%% 纯硬件 AI 加速器 (Patch -> 12层Encoder -> Head)...\n");
    // 💡 这里我保留了你测试用的参数 '3'。如果你想跑完整的 12 层验证，请把 '3' 改为 NUM_LAYERS。
    vit_block_top(mock_ddr_weights, i_stream, o_stream_logits, NUM_LAYERS);

    int hw_logits[1000];
    for(int i = 0; i < 1000; i++) {
        hw_logits[i] = o_stream_logits.read().data;
    }

    printf("\n--- C-Sim Final Logits Compare ---\n");
    bool flag = true;
    for(int i = 0; i < 1000; i++) {
        int hw_val = hw_logits[i] & 0x7FFFF;
        if (hw_val >= 262144) hw_val -= 524288;

        if (i < 20) {
            printf("Logit[%4d] HW: %8d | REF: %8d  %s\n",
                   i, hw_val, ref_logits[i], (hw_val == ref_logits[i]) ? "(MATCH)":"(MISMATCH)");
        }
        if(hw_val != ref_logits[i]) flag = false;
    }

    int max_val = -9999999;
    int max_id = -1;
    for(int i=0; i<1000; i++){
        int val = hw_logits[i] & 0x7FFFF;
        if (val >= 262144) val -= 524288;
        if(val > max_val) { max_val = val; max_id = i; }
    }
    printf("\n FPGA class ID: %d \n", max_id);

    if(flag) {
        printf("=======================================\n");
        printf("   PASS! \n");
        printf("=======================================\n");
    } else {
        printf("❌ FAIL!  Mismatch。\n");
    }

    delete[] mock_ddr_weights;
    delete[] input_data; delete[] ref_logits;

    return 0;
}
#endif
