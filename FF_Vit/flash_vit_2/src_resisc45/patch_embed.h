#ifndef __INT_PATCH_EMBED_H__
#define __INT_PATCH_EMBED_H__

#include "common.h"
#include "dataflow.h"
template<
    class   __if_t,                     // input feature map type
    class   __we_t,                     // weight type
    class   __bi_t,                     // the same type for cls
    class   __mc_t,                     // mac type
    class   __of_t,                     // output type
    int     T,                          // input  feature map sequence length
    int     TP,                         // input  feature map sequence parallel degree
    int     CI,                         // input  feature map channel
    int     CIP,                        // input  feature map channel parallel degree
    int     CIAP,
    int     CO,                         // output feature map channel
    int     COP,                        // output feature map channel parallel degree
    int     COAP,
    bool    USE_DSP                     // use DSP or not
>
class PatchEmbed{
public:
    static_assert(CI % CIP == 0, "CI must be multiple of CIP");
    static_assert(CO % COP == 0, "CO must be multiple of COP");

    static constexpr int CIT = CI / CIP;
    static constexpr int COT = CO / COP;
    static constexpr int TT  = T  / TP;

    __we_t weight_arr   [CO][CI];
    __bi_t bias_arr     [T][CO];    
    __bi_t cls_arr      [CO];       

    int s;
    int b;

    explicit PatchEmbed() {}

    void load_weights_from_bram(const PatchEmbedWeights* w) {
        #pragma HLS inline off
        s = w->scalars[0];
        b = (s > 0) ? (1 << (s - 1)) : 0;
        
        // ==========================================
        // 🚀 核心优化 1：彻底消灭 / 和 %，拯救海量 LUT 资源！
        // 因为 CI(768) 等通常不是 2 的幂次，除法器会消耗极多硬件。
        // 改用纯加法和比较逻辑（硬件上只需极简单的比较器和累加器）
        // ==========================================
        int co = 0;
        int ci = 0;
        for(int i = 0; i < CO * CI; ++i){
            #pragma HLS pipeline II=1
            weight_arr[co][ci] = w->weight[i];
            if (ci == CI - 1) {
                ci = 0;
                co++;
            } else {
                ci++;
            }
        }

        int t = 0;
        int co_b = 0;
        for(int i = 0; i < T * CO; ++i){
            #pragma HLS pipeline II=1
            bias_arr[t][co_b] = w->bias[i];
            if (co_b == CO - 1) {
                co_b = 0;
                t++;
            } else {
                co_b++;
            }
        }

        for(int co_c = 0; co_c < CO; ++co_c){
            #pragma HLS pipeline II=1
            cls_arr[co_c] = w->cls[co_c];
        }
    }


    void step2_mac_replace_shift(hls::stream<hls::vector<__if_t, TP*CIP> >&i_stream, hls::stream<hls::vector<__of_t, TP*COP> >& o_stream) const {

        #pragma HLS array_reshape variable=weight_arr   cyclic factor=COP dim=1
        #pragma HLS array_reshape variable=weight_arr   cyclic factor=CIP dim=2
        #pragma HLS bind_storage variable=weight_arr    type=ram_1p impl=BRAM

        #pragma HLS array_reshape   variable=bias_arr   cyclic factor=TP  dim=1
        #pragma HLS array_reshape   variable=bias_arr   cyclic factor=COP dim=2
        #pragma HLS bind_storage    variable=bias_arr   type=ram_1p impl=BRAM

        #pragma HLS array_reshape   variable=cls_arr    cyclic factor=COP dim=1

        __mc_t acc_buf[COT][TP][COP];
        #pragma HLS array_partition variable=acc_buf complete dim=2
        #pragma HLS array_partition variable=acc_buf complete dim=3

        TT_LOOP: for(int tt=0;tt<TT; ++tt){
            
            CIT_LOOP: for(int cit=0; cit<CIT; ++cit){
                
                hls::vector<__if_t, TP*CIP> vec_i = i_stream.read();

                COT_LOOP: for(int cot=0; cot<COT; ++cot){
                    #pragma HLS pipeline II=1

                    for(int tp=0; tp<TP; ++tp){
                        #pragma HLS unroll factor=2
                        for(int cop=0; cop<COP; ++cop){
                            #pragma HLS unroll factor=2
                            
                            __mc_t sum = 0;
                            for(int cip=0; cip<CIP; ++cip){
                                #pragma HLS unroll
                                auto a_val = vec_i[tp*CIP + cip];
                                auto w_val = weight_arr[cot*COP + cop][cit*CIP + cip];
                                auto mul_res = a_val * w_val;
                                
                                // ==========================================
                                // 🚀 核心优化 2：适度且高效地使用 DSP
                                // ==========================================
                                if(USE_DSP){
                                    // 绑定乘法到 DSP
                                    #pragma HLS bind_op variable=mul_res op=mul impl=dsp
                                } else {
                                    // 绑定乘法到 LUT
                                    #pragma HLS bind_op variable=mul_res op=mul impl=fabric
                                }
                                sum += mul_res;
                            }

                            if(cit == 0){
                                __mc_t init_val = 0;
                                if(!(tt == 0 && tp == 0)){
                                    init_val = bias_arr[tt*TP + tp][cot*COP + cop];
                                }
                                acc_buf[cot][tp][cop] = init_val + sum;
                            } else {
                                // 如果使用了 DSP，HLS 通常会自动把外层的 += sum 吸收到 DSP48 的加法器里
                                acc_buf[cot][tp][cop] += sum;
                            }
                        }
                    }
                } // end of COT_LOOP
            } // end of CIT_LOOP

            WRITE_COT_LOOP: for(int cot=0; cot<COT; ++cot){
                #pragma HLS pipeline II=1
                hls::vector<__of_t, TP*COP> vec_o_shift;
                
                for(int tp=0; tp<TP; ++tp){
                    #pragma HLS unroll
                    for(int cop=0; cop<COP; ++cop){
                        #pragma HLS unroll
                        
                        __mc_t final_val = acc_buf[cot][tp][cop];
                        
                        if(tt == 0 && tp == 0){
                            final_val = cls_arr[cot*COP + cop];
                        }
                        
                        vec_o_shift[tp*COP + cop] = (final_val + b) >> s;
                    }
                }
                o_stream.write(vec_o_shift);
            } // end of WRITE_COT_LOOP

        } // end of TT_LOOP
    }

    void do_patch_embed(hls::stream<hls::vector<__if_t, TP*CIAP> > &i_stream, hls::stream<hls::vector<__of_t, TP*COAP> > &o_stream) const {
        #pragma HLS dataflow

        Adapter<__if_t, T, TP, CI, CIAP, CIP> adapter_i;
        Adapter<__of_t, T, TP, CO, COP, COAP> adapter_o;

        hls::stream<hls::vector<__if_t, TP*CIP> >   adpt_sm             ("adpt_sm"             );
        hls::stream<hls::vector<__of_t, TP*COP> >   mac_sm              ("mac_sm"              );

        #pragma HLS stream variable=adpt_sm             depth=64
        #pragma HLS stream variable=mac_sm              depth=2

        adapter_i.do_adapt          (   i_stream,           adpt_sm             );
        step2_mac_replace_shift     (   adpt_sm,            mac_sm              );
        adapter_o.do_adapt          (   mac_sm,             o_stream            );
    }
};

#endif