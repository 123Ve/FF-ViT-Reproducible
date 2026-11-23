#ifndef __INT_SOFTMAX_H__
#define __INT_SOFTMAX_H__

#include "common.h"
#include "utils.h"

template<
    class   __if_t,             // input feature map data type
    class   __minus_t,          // second pass, x-xmax type
    class   __cursor1_t,        // lookup table 1 cursor type, after shift
    class   __exp_t,            // lookup table 1 exp type
    class   __acc_t,            // sum(exp x- xmax)
    class   __recip_t,
    class   __cursor2_one_t,    // table 1
    class   __cursor2_two_t,    // table 2
    class   __affine_t,            // max{mul_one,mul_two}
    class   __cursor3_t,        // max{cursor3_one,cursor3_two}
    class   __of_t,
    int     ENTRIES_EXP,
    int     ENTRIES_RECIP,
    int     T,
    int     TP,
    int     C,
    int     CP
> class Softmax{
public:

    // static assertions
    static_assert(T % TP == 0, "T must be multiple of TP");
    static_assert(C % CP == 0, "C must be multiple of CP");

    // static hyper parameters
    static constexpr int TT = T / TP;
    static constexpr int CT = C / CP;

    int local_scalars[14];


    __exp_t     local_exp_table       [ENTRIES_EXP];
    __recip_t   local_recip_table_one [ENTRIES_RECIP];
    __recip_t   local_recip_table_two [ENTRIES_RECIP];


    explicit Softmax(){}

    __if_t  buffer      [TP][C];
    __exp_t exp_score   [TP][C];

    void do_softmax(hls::stream<hls::vector<__if_t, TP*CP> >& i_stream, hls::stream<hls::vector<__of_t, TP*CP> >& o_stream){
        #pragma HLS array_reshape variable=buffer      dim=1 complete
        #pragma HLS array_reshape variable=buffer      dim=2 cyclic factor=CP
		#pragma HLS bind_storage  variable=buffer      type=ram_2p impl=bram
        #pragma HLS array_reshape variable=exp_score   dim=1 complete
        #pragma HLS array_reshape variable=exp_score   dim=2 cyclic factor=CP
		#pragma HLS bind_storage  variable=exp_score      type=ram_2p impl=bram



        int b1          = local_scalars[0];
        int s1          = local_scalars[1];
        int bound1      = local_scalars[2];

        int b2_one      = local_scalars[3];
        int s2_one      = local_scalars[4];
        int bound2_one  = local_scalars[5];
        int b3_one      = local_scalars[6];
        int s3_one      = local_scalars[7];

        int b2_two      = local_scalars[8];
        int s2_two      = local_scalars[9];
        int bound2_two  = local_scalars[10];
        int b3_two      = local_scalars[11];
        int s3_two      = local_scalars[12];
        int clamp_bits  = local_scalars[13];

        __if_t      max_val     [TP];
        __acc_t     acc_val     [TP];
        __recip_t   recip_val   [TP];
        bool        in_two      [TP];

        TT_LOOP:for(int tt=0; tt<TT; ++tt){
            STATE_LOOP:for(int state=0; state<3; ++state){
                CT_LOOP:for(int ct=0; ct<CT; ++ct){
                    #pragma HLS pipeline II = 1

                    if(state == 0){
                        // first pass, read in, find max, store in buffer

                        //read in
                        hls::vector<__if_t, CP*TP> vec_i = i_stream.read();

                        // init max val
                        if(ct == 0){
                            for(int tp=0; tp<TP; ++tp){
                            #pragma HLS unroll
                                max_val[tp] = vec_i[tp*CP + 0];
                            }
                        }

                        // find max and store in buffer
                        for(int tp=0; tp<TP; ++tp){
                            #pragma HLS unroll
                            for(int cp=0; cp<CP; ++cp){
                                #pragma HLS unroll
                                // store in buffer
                                buffer[tp][ct*CP + cp] = vec_i[tp*CP + cp];
                                // find max
                                max_val[tp] = max(max_val[tp], vec_i[tp*CP + cp]);
                            }
                        }

                    }

                    else if(state == 1){
                        // second pass, exp(x-xmax), sum(exp(x-xmax)), recip(sum(exp(x-xmax)))

                        // init acc
                        if(ct == 0){
                            for(int tp=0; tp<TP; ++tp){
                            #pragma HLS unroll
                                acc_val[tp] = 0;
                            }
                        }

                        for(int tp=0; tp<TP; ++tp){
                            #pragma HLS unroll
                            for(int cp=0; cp<CP; ++cp){
                                #pragma HLS unroll

                                __minus_t minus = max_val[tp] - buffer[tp][ct*CP + cp]; // opposite minus
                                __cursor1_t cursor = (minus + b1) >> s1;
                                cursor = clamp(cursor, 0, bound1);
                                exp_score[tp][ct*CP + cp] = local_exp_table[cursor];
                                acc_val[tp] += local_exp_table[cursor];
                            }
                        }

                        if(ct == CT-1){ // look up recip table
                            for(int tp=0; tp<TP; ++tp){
                                __cursor2_one_t cursor_one = (acc_val[tp] + b2_one) >> s2_one;
                                if(cursor_one > bound2_one){
                                    in_two[tp] = 1;
                                    __cursor2_two_t cursor_two = (acc_val[tp] + b2_two) >> s2_two;
                                    cursor_two = clamp(cursor_two, 0, bound2_two);
                                    recip_val[tp] = local_recip_table_two[cursor_two];
                                } else {
                                    in_two[tp] = 0;
                                    cursor_one = clamp(cursor_one, 0, bound2_one);
                                    recip_val[tp] = local_recip_table_one[cursor_one];
                                }
                            }
                        }

                    }

                    else if(state == 2){
                        // third pass, mul and requant

                        // write out
                        hls::vector<__of_t,CP*TP> o_vec;

                        for(int tp=0; tp<TP; ++tp){
                            #pragma HLS unroll
                            for(int cp=0; cp<CP; ++cp){
                                #pragma HLS unroll

                                __affine_t val = exp_score[tp][ct*CP + cp] * recip_val[tp];
                                // __cursor3_t rel_one = (val + b3_one) >> s3_one;
                                // __cursor3_t rel_two = (val + b3_two) >> s3_two;
                                // __cursor3_t rel = (in_two[tp] == 1) ? rel_two : rel_one;
                                int rel_b3 = (in_two[tp] == 1) ? b3_two : b3_one;
                                int rel_s3 = (in_two[tp] == 1) ? s3_two : s3_one;
                                __cursor3_t rel = (val + rel_b3) >> rel_s3;
                                o_vec[tp*CP + cp] = quantize_clamp(rel, clamp_bits, false);
                            }
                        }
                        o_stream.write(o_vec);
                    }

                } // end of CT loop
            } // end of state loop
        } // end of TT loop

    }

};

#endif
