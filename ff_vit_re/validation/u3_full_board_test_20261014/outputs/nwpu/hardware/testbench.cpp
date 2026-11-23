// Single C-sim translation unit; the frozen arithmetic source is unmodified.
#define main original_embedded_testbench_main
#include "block0.cpp"
#undef main
#include <fstream>
#include <stdexcept>
#include <vector>
#include <cstdio>
#include <cstdint>

template<class T> void read_exact(const char* name, std::vector<T>& data) {
    std::ifstream f(name, std::ios::binary | std::ios::ate);
    if (!f || f.tellg() != std::streamoff(sizeof(T)*data.size()))
        throw std::runtime_error(std::string("invalid fixture size: ")+name);
    f.seekg(0);
    if (!f.read(reinterpret_cast<char*>(data.data()), sizeof(T)*data.size()))
        throw std::runtime_error("fixture read failed");
}
int main() {
    try {
        static_assert(sizeof(BlockLayerWeights)==231008, "weight ABI mismatch");
        static_assert(sizeof(int)==4, "32-bit int required");
        const uint16_t endian=1;
        if (*reinterpret_cast<const uint8_t*>(&endian)!=1)
            throw std::runtime_error("little endian required");
        std::vector<BlockLayerWeights> weights(12);
        std::vector<int16_t> input(196*768);
        std::vector<int32_t> expected(1000), actual(1000);
        read_exact("weights.bin",weights);
        read_exact("input_dma.bin",input);
        read_exact("expected.bin",expected);
        for (int repeat=0; repeat<2; ++repeat) {
            hls::stream<axis_in_pkt> in;
            hls::stream<hls::axis<int,0,0,0>> out;
            for(int tt=0;tt<98;++tt) for(int c=0;c<768;++c) {
                axis_in_pkt p;
                for(int tp=0;tp<2;++tp) p.data[tp]=input[(tt*768+c)*2+tp];
                p.keep=-1; p.strb=-1; p.last=(tt==97 && c==767);
                in.write(p);
            }
            vit_block_top(weights.data(),in,out,12);
            int mismatch=0;
            for(int i=0;i<1000;++i) {
                if(out.empty()) throw std::runtime_error("truncated stream");
                auto packet=out.read();
                if(bool(packet.last)!=(i==999)) throw std::runtime_error("incorrect TLAST");
                actual[i]=packet.data;
                if(actual[i]!=expected[i]) {
                    if(mismatch<4) std::printf("CODE_DIFF class=%d actual=%d golden=%d\n",i,actual[i],expected[i]);
                    ++mismatch;
                }
            }
            if(!in.empty() || !out.empty()) throw std::runtime_error("unexpected stream tail");
            std::ofstream dump(repeat?"csim_repeat_logits.bin":"csim_logits.bin",std::ios::binary);
            dump.write(reinterpret_cast<const char*>(actual.data()),4000);
            if(!dump) throw std::runtime_error("output write failed");
            std::printf("U3_CSIM_REPEAT=%d LOGIT_MISMATCHES=%d\n",repeat,mismatch);
            if(mismatch) return 1;
        }
        std::puts("U3_CSIM_BIT_EXACT_PASS");
        return 0;
    } catch(const std::exception& e) {
        std::fprintf(stderr,"U3_CSIM_ERROR=%s\n",e.what()); return 2;
    }
}
