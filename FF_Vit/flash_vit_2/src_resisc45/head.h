#ifndef __INT_H__
#define __INT_H__

#include "common.h"
#include "layernorm.h"
#include "matmul.h"
#include "dataflow.h" // 引入 HeadWeights

using namespace std;

template<
    // global shapes
    int     T,                  int     TP,
    int     CI,                 int     CIAP,
    int     CO,                 int     COAP,

    // global types
    class   __if_t,             class   __ln_t,
    class   __we_t,             class   __bi_t,
    class   __mc_t,

    // layernorm
    class   __ln_sum_t,         class   __ln_divc_t,
    class   __ln_mu_t,          class   __ln_var_t,
    class   __ln_cursor_t,      class   __ln_rsqrt_t,
    class   __ln_affine_t,      class   __ln_shift_t,
    int     LN_ENTRIES_RSQRT,

    // matmul
    int     CIP,             int     COP,
    int     ADPT_FIFO_DEPTH, int     WIND_FIFO_DEPTH,
    int     WGHT_FIFO_DEPTH, int     MACS_FIFO_DEPTH,
    bool    USE_DSP
> class Head{
public:
    static_assert(  CI  % CIAP      == 0, "C must be multiple of CIAP");
    static_assert(  CO  % COAP      == 0, "C must be multiple of COAP");
    static_assert(  T   % TP        == 0, "T must be multiple of TP");
    static_assert(  CI  % CIP       == 0, "C must be multiple of CIP");
    static_assert(  CO  % COP       == 0, "C must be multiple of COP");

    static constexpr int TT     = T / TP;
    static constexpr int CIAT   = CI / CIAP;
    static constexpr int COAT   = CO / COAP;

    Layernorm<
        __if_t, __ln_sum_t, __ln_divc_t, __ln_mu_t, __ln_var_t, __ln_cursor_t,
        __ln_rsqrt_t, __ln_affine_t, __ln_shift_t, __ln_t, LN_ENTRIES_RSQRT,
        1, 1, CI, CIAP
    > lnq;

    Matmul<
        __ln_t, __we_t, __bi_t, __mc_t, 1, 1, CI, CIP, CIAP, CO, COP, COAP,
        ADPT_FIFO_DEPTH, WIND_FIFO_DEPTH, WGHT_FIFO_DEPTH, MACS_FIFO_DEPTH,
        BRAM_STYLE, USE_DSP
    > matmul;

    explicit Head() {}


    void load_weights_from_bram(const HeadWeights* w) {
        #pragma HLS inline off

        // for(int i=0; i<8; i++) {
        //     #pragma HLS unroll
        //     this->lnq.local_scalars[i] = w->ln_scalars[i];
        // }
        for(int i=0; i<8; i++) {
             #pragma HLS pipeline II=1 // 必须用 pipeline，让硬件顺序 Burst
             this->lnq.local_scalars[i] = w->ln_scalars[i];
        }
// 🚨 修复 AXI 端口冲突：将 lnw 和 lnb 分开读取，完美达成连续 Burst！
        for(int i=0; i<CI; i++) {
            #pragma HLS pipeline II=1
            this->lnq.local_lnw_ram[i] = w->ln_lnw[i];
        }

        for(int i=0; i<CI; i++) {
            #pragma HLS pipeline II=1
            this->lnq.local_lnb_ram[i] = w->ln_lnb[i];
        }
        for(int i=0; i<LN_ENTRIES_RSQRT; i++) {
            #pragma HLS pipeline II=1
            this->lnq.local_rsqrt_table[i] = w->ln_rsqrt_table[i];
        }

        // ==========================================
        // 🚀 核心修复：分离并展平循环，完美打满 AXI 总线带宽
        // ==========================================
        
        // 1. 单独用一个 1D 循环加载 Bias
        for(int co=0; co<CO; co++) {
            #pragma HLS pipeline II=1
            this->matmul.local_bias_ram[co] = w->bias[co];
        }

        // 2. 将二维的 Weight 加载展平为 1D 循环，不含有任何打断流水线的分支
        // int co_w = 0;
        // int ci_w = 0;
        // for(int i=0; i < CO * CI; i++) {
        //     #pragma HLS pipeline II=1
        //     this->matmul.local_weight_ram[co_w][ci_w] = w->weight[i];
            
        //     // 手动维护二维坐标
        //     if(ci_w == CI - 1) {
        //         ci_w = 0;
        //         co_w++;
        //     } else {
        //         ci_w++;
        //     }
        // }
        for(int co = 0; co < CO; co++) {
    for(int ci = 0; ci < CI; ci++) {
        #pragma HLS pipeline II=1
        this->matmul.local_weight_ram[co][ci] = w->weight[co * CI + ci];
    }
}
    }

    void select_cls(
        hls::stream<hls::vector<__if_t, TP*CIAP> >& i_stream,
        hls::stream<hls::vector<__if_t, CIAP> >& o_stream
    ){
        TT_LOOP: for(int tt=0; tt<TT; ++tt){
            CIAT_LOOP: for(int ciat=0; ciat<CIAT; ++ciat){
                #pragma HLS pipeline II=1
                hls::vector<__if_t, TP*CIAP> vec_i = i_stream.read();
                if(tt==0){
                    hls::vector<__if_t, CIAP> vec_o;
                    for(int ciap=0; ciap<CIAP; ++ciap){
                        #pragma HLS unroll
                        vec_o[ciap] = vec_i[ciap];
                    }
                    o_stream.write(vec_o);
                }
            }
        }
    }

    void do_head(
        hls::stream<hls::vector<__if_t, TP*CIAP> >& i_stream,
        hls::stream<hls::vector<__mc_t,    COAP> >& o_stream
    ) {
        #pragma HLS dataflow
        hls::stream<hls::vector<__if_t, CIAP    > > cls_sm  ("cls_sm");
        hls::stream<hls::vector<__ln_t, CIAP    > > ln_sm   ("ln_sm");
        #pragma HLS stream variable=cls_sm     depth=2
        #pragma HLS stream variable=ln_sm      depth=2

        this->select_cls ( i_stream, cls_sm );
        lnq.do_layernorm ( cls_sm,   ln_sm  );
        matmul.do_matmul ( ln_sm,    o_stream );
    }
};

#endif
