
#ifndef __INT_LAYERNORM_H__
#define __INT_LAYERNORM_H__
#include "common.h"
#include "utils.h"

template<
    class   __if_t,         // input feature map data type
    class   __sum_t,        // sum type
    class   __divc_t,       // type of sum(x) * C_1_m
    class   __mu_t,         // type of x mean
    class   __var_t,        // type of pow diff sum
    class   __cursor_t,     // (varx + b) >> s1
    class   __rsqrt_t,      // lookup table data
    class   __affine_t,     // (x-mu) * local_rsqrt_table * local_lnw + local_lnb
    class   __shift_t,      // >> s2
    class   __of_t,         // output
    int     ENTRIES_RSQRT,
    int     T,              // input  feature map token
    int     TP,             // input  feature map token  parallel degree
    int     C,              // input  feature map channel
    int     CP>             // input  feature map channel parallel degree
class Layernorm{
public:

    // static assertions
    static_assert(T % TP == 0, "T must be multiple of TP");
    static_assert(C % CP == 0, "C must be multiple of CP");

    // static hyper parameters
    static constexpr int TT = T / TP;
    static constexpr int CT = C / CP;




    int         local_scalars[7];
    __rsqrt_t   local_rsqrt_table[ENTRIES_RSQRT];
    int         local_lnw_ram[C];
    long long   local_lnb_ram[C];



    explicit Layernorm(){
    }



    void do_layernorm(hls::stream<hls::vector<__if_t, CP*TP> >& i_stream, hls::stream<hls::vector<__of_t, CP*TP> >& o_stream){


        // local_lnw
        #pragma HLS array_reshape   variable=local_lnw_ram            dim=1 cyclic factor=CP
        #pragma HLS bind_storage    variable=local_lnw_ram            type=ram_1p impl=lutram

        // local_lnb
        #pragma HLS array_reshape   variable=local_lnb_ram            dim=1 cyclic factor=CP
        #pragma HLS bind_storage    variable=local_lnb_ram            type=ram_1p impl=lutram

        // local_rsqrt_table
        #pragma HLS bind_storage    variable=local_rsqrt_table        type=ram_2p impl=lutram



        int C_1_m       = local_scalars[0];
        int C_1_s       = local_scalars[1];
        int b           = local_scalars[2];
        int s1          = local_scalars[3];
        int bound       = local_scalars[4];
        int s2          = local_scalars[5];
        int clamp_bits  = local_scalars[6];

        // buffer
        __if_t      buffer  [TP][C];
        #pragma HLS array_reshape   variable=buffer         dim=1 complete
        #pragma HLS array_reshape   variable=buffer         dim=2 cyclic factor=CP
        #pragma HLS bind_storage    variable=buffer         type=ram_2p impl=bram

        // other
        __mu_t      mean    [TP];
        __rsqrt_t   st_sqrt [TP];
        __sum_t     acc     [TP];
        long long   sum_sq  [TP];
        __var_t     sum     [TP];
        #pragma HLS array_partition variable=mean    complete
        #pragma HLS array_partition variable=st_sqrt complete
        #pragma HLS array_partition variable=acc     complete
        #pragma HLS array_partition variable=sum_sq  complete
        #pragma HLS array_partition variable=sum     complete

        TT_LOOP:for(int tt=0; tt<TT; tt++){
            STATE_LOOP: for(int state=0; state<2; state++){
                CT_LOOP:for(int ct=0; ct<CT; ct++){
                    #pragma HLS pipeline II = 1

                    if(state == 0){
                        // First pass: buffer input and collect both sum(x) and sum(x*x).

                        // read in
                        hls::vector<__if_t, CP*TP> vec_i = i_stream.read();

                        // init accumulators
                        if(ct == 0){
                            for(int tp=0; tp<TP; tp++){
                                #pragma HLS unroll
                                acc[tp] = 0;
                                sum_sq[tp] = 0;
                            }
                        }

                        // buffer, mean accumulator and squared-sum accumulator
                        for(int tp=0; tp<TP; tp++){
                            #pragma HLS unroll
                            for(int cp=0; cp<CP; cp++){
                                #pragma HLS unroll
                                __if_t x = vec_i[tp*CP + cp];
                                buffer[tp][ct*CP + cp] = x;
                                acc[tp] += x;
                                long long x_wide = (long long)x;
                                sum_sq[tp] += x_wide * x_wide;
                            }
                        }

                        // Divide by C and derive sum((x - mean)^2) without a second scan.
                        if(ct == CT-1) {
                            for(int tp=0; tp<TP; tp++){
                                #pragma HLS unroll
                                __divc_t tmp = acc[tp] * C_1_m;
                                tmp += (1 << (C_1_s - 1));
                                mean[tp] = tmp >> C_1_s;

                                long long mean_wide = (long long)mean[tp];
                                long long acc_wide = (long long)acc[tp];
                                long long var_wide =
                                    sum_sq[tp] - 2LL * mean_wide * acc_wide +
                                    (long long)C * mean_wide * mean_wide;
                                sum[tp] = (__var_t)var_wide;

                                __cursor_t cursor = (sum[tp] + b) >> s1;
                                cursor = clamp(cursor, 0, bound);
                                st_sqrt[tp] = local_rsqrt_table[cursor];
                            }
                        }
                    }

                    else if(state == 1){
                        // Second pass: normalize, apply affine transform and rescale.

                        hls::vector<__of_t,CP*TP> o_vec;

                        for(int tp=0; tp<TP; tp++){
                        #pragma HLS unroll
                            for(int cp=0; cp<CP; cp++){
                                #pragma HLS unroll
                                __if_t diff = buffer[tp][ct*CP + cp] - mean[tp]; 
                                // __affine_t mul = diff * st_sqrt[tp] * local_lnw_ram[ct*CP + cp];
                                // __affine_t val = mul + local_lnb_ram[ct*CP + cp];
                                __affine_t val = diff * st_sqrt[tp] * local_lnw_ram[ct*CP + cp] + local_lnb_ram[ct*CP + cp];
                                __shift_t rel = val >> s2;
                                o_vec[tp*CP + cp] = quantize_clamp(rel, clamp_bits, true);
                            }
                        }
                        o_stream.write(o_vec);
                    }

                } // end of CT_LOOP
            } // end of STATE_LOOP
        } // end of TT_LOOP

    }
};
#endif
