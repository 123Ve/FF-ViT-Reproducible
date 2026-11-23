// Vitis C-sim compiles this self-contained testbench translation unit.
// The architecture source stays byte-identical, including its legacy TB.
#define main original_embedded_testbench_main
#include "src/block0.cpp"
#undef main
#include <fstream>
#include <stdexcept>
#include <vector>
#include <cstdio>
#include <cstdint>

template<class V> void read_exact(const char* path,V* data,size_t count) {
    std::ifstream input(path,std::ios::binary|std::ios::ate);
    if(!input || input.tellg()!=std::streamoff(sizeof(V)*count))
        throw std::runtime_error(std::string("wrong size or missing: ")+path);
    input.seekg(0);
    if(!input.read(reinterpret_cast<char*>(data),sizeof(V)*count))
        throw std::runtime_error(std::string("read failed: ")+path);
}

int main() {
    try {
        static_assert(sizeof(int)==4,"requires 32-bit int");
        static_assert(sizeof(BlockLayerWeights)==231008,"native weight ABI mismatch");
        const uint16_t one=1;
        if(*reinterpret_cast<const uint8_t*>(&one)!=1) throw std::runtime_error("requires little endian");
        std::vector<BlockLayerWeights> weights(12);
        std::vector<int16_t> input(196*768);
        std::vector<int32_t> expected(1000),actual(1000);
        read_exact("weights.bin",weights.data(),weights.size());
        read_exact("input.bin",input.data(),input.size());
        read_exact("output.bin",expected.data(),expected.size());
        hls::stream<axis_in_pkt> in("fixture_input");
        hls::stream<hls::axis<int,0,0,0>> out("fixture_logits");
        for(int tt=0;tt<98;++tt) for(int c=0;c<768;++c) {
            axis_in_pkt p;
            for(int tp=0;tp<2;++tp) p.data[tp]=input[(tt*2+tp)*768+c];
            p.keep=-1;p.strb=-1;p.last=(tt==97 && c==767);
            in.write(p);
        }
        vit_block_top(weights.data(),in,out,12);
        int mismatches=0;
        for(int i=0;i<1000;++i) {
            if(out.empty()) throw std::runtime_error("truncated output stream");
            actual[i]=out.read().data;
            if(actual[i]!=expected[i]) ++mismatches;
        }
        if(!in.empty() || !out.empty()) throw std::runtime_error("unexpected stream tail");
        std::ofstream dump("hls_logits.bin",std::ios::binary);
        dump.write(reinterpret_cast<const char*>(actual.data()),actual.size()*sizeof(int32_t));
        if(!dump) throw std::runtime_error("logit write failed");
        std::printf("HLS_LOGIT_MISMATCHES=%d\n",mismatches);
        return mismatches ? 1 : 0;
    } catch(const std::exception& e) {
        std::fprintf(stderr,"HLS_TB_ERROR=%s\n",e.what());return 2;
    }
}
