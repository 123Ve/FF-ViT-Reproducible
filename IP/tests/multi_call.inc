// C/RTL test only. Mutations caught: wrong layer/buffer, stale state, missing logits,
// wrong TLAST and numerical changes. Frame 1 is different input, not new weights.
#include <cstdio>
#include <cstdlib>
#include <string>
#include <algorithm>
int main(int argc, char** argv) {
    const std::string fixtures = argc > 1 ? argv[1] : ".";
    const std::string out = argc > 2 ? argv[2] : "e04_logits.csv";
    const std::string ref = argc > 3 ? argv[3] : "e04_reference.csv";
    const bool generate = ref == "GENERATE";
    BlockLayerWeights* weights = new BlockLayerWeights[12]();
    int* pixels = new int[T*768];
    int expected[1000];
    auto read_exact = [&](const char* name, void* ptr, size_t size, size_t n) {
        std::string path = fixtures + "/" + name;
        FILE* f = std::fopen(path.c_str(), "rb");
        if (!f) { std::perror(path.c_str()); std::exit(2); }
        if (std::fread(ptr, size, n, f) != n || std::fgetc(f) != EOF) std::exit(2);
        std::fclose(f);
    };
    read_exact("weights.bin", weights, sizeof(BlockLayerWeights), 12);
    read_exact("input.bin", pixels, sizeof(int), T*768);
    read_exact("output.bin", expected, sizeof(int), 1000);
    FILE* dst = std::fopen(out.c_str(), "w");
    FILE* golden = generate ? nullptr : std::fopen(ref.c_str(), "r");
    if (!dst || (!generate && !golden)) { std::perror("outputs/reference"); return 2; }
    int mismatches = 0;
    for (int frame = 0; frame < 3; ++frame) {
        hls::stream<axis_in_pkt> input("e04_input");
        hls::stream<hls::axis<int,0,0,0>> output("e04_output");
        for (int tt = 0; tt < T/TP; ++tt) for (int c = 0; c < 768; ++c) {
            axis_in_pkt packet;
            for (int tp = 0; tp < TP; ++tp) {
                int index = (tt*TP+tp)*768+c;
                packet.data[tp] = pixels[frame == 1 ? T*768-1-index : index];
            }
            packet.keep = -1; packet.strb = -1; packet.last = 0;
            input.write(packet);
        }
        vit_block_top(weights, input, output, 12);
        if (!input.empty()) return 3;
        for (int i = 0; i < 1000; ++i) {
            if (output.empty()) return 3;
            auto pkt = output.read();
            int raw = (int)pkt.data;
            int canon = raw & 0x7ffff;
            if (canon >= 262144) canon -= 524288;
            if ((bool)pkt.last != (i == 999)) return 3;
            if (frame != 1 && canon != expected[i]) ++mismatches;
            if (golden) {
                int rf, ri, rv;
                if (std::fscanf(golden, "%d,%d,%d", &rf, &ri, &rv) != 3) return 3;
                if (rf != frame || ri != i || rv != raw) ++mismatches;
            }
            std::fprintf(dst, "%d,%d,%d\n", frame, i, raw);
        }
        if (!output.empty()) return 3;
        std::printf("E04 frame=%d layers=12 logits=1000 cumulative_mismatch=%d\n", frame, mismatches);
        std::fflush(stdout);
    }
    if (golden) { int extra; if (std::fscanf(golden, "%d", &extra) != EOF) return 3; std::fclose(golden); }
    std::fclose(dst); delete[] weights; delete[] pixels;
    return mismatches ? 1 : 0;
}
