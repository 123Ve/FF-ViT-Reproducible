#ifndef __INT_QUANT_H__
#define __INT_QUANT_H__

#include "common.h"
#include "utils.h"

template<
    class __if_t,       // input feature map data type
    class __cursor_t,   // lookup table cursor type
    class __of_t,       // output feature map data type
    int   T,            // input feature map sequence length
    int   TP,           // input feature map sequence parallel degree
    int   C,            // input feature map channel
    int   CP,           // input feature map channel parallel degree
    int   ENTRIES       // lookup table entries
> class Quant{
public:

    // static assertions
    static_assert(C % CP == 0, "C must be multiple of CP");

    // static hyper parameters
    static constexpr int CT = C / CP;
    static constexpr int TT = T / TP;

    int    local_scalars[4];
    __of_t local_table[ENTRIES];

    explicit Quant() {

    }

    void do_quant(hls::stream<hls::vector<__if_t, TP*CP> >& i_stream, hls::stream<hls::vector<__of_t, TP*CP> >& o_stream) const {


    	    // 🚨 删掉/注释掉旧的 bind_storage，改用 complete 展开
    	 #pragma HLS bind_storage variable=local_table type=ram_2p impl=lutram
    	//#pragma HLS array_partition variable=local_table complete

        int b     = local_scalars[0];
        int s     = local_scalars[1];
        int bound = local_scalars[2];

        TT_LOOP: for(int tt=0; tt<TT; ++tt){
            CT_LOOP: for(int ct=0; ct<CT; ++ct){
                #pragma HLS pipeline II=1

                // read input
                hls::vector<__if_t, TP*CP> vec_i = i_stream.read();
                hls::vector<__of_t, TP*CP> vec_o;

                // calculate cursor and lookup
                for(int tp=0; tp<TP; ++tp){
                    #pragma HLS unroll
                    for(int cp=0; cp<CP; ++cp){
                        #pragma HLS unroll
                        

                        __cursor_t cursor = (vec_i[tp*CP + cp] + b) >> s;
                        cursor = clamp(cursor, 0, bound);
                        
                        // 浠庡彲璇诲啓鐨� local_table 涓煡琛�
                        vec_o[tp*CP + cp] = local_table[cursor];
                    }
                }

                // write output
                o_stream.write(vec_o);

            } // end of CT_LOOP
        } // end of TT_LOOP

    }

};

#endif
