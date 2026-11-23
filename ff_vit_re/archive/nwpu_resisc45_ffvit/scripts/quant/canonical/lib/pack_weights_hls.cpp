#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <vector>
#include <cstddef>
#include <cstring>

// Audited dataflow.h layout, with portable host storage for each 128-bit word.
// These declarations are independent of Python's serialized field ordering.
struct alignas(16) Pack128_3 { unsigned __int128 d; };
struct alignas(16) Pack128_16 { unsigned __int128 d; };
struct AttnLayerWeights {
    Pack128_3 q_weight[1152], k_weight[1152], v_weight[1152];
    Pack128_16 q_bias[24], k_bias[24], v_bias[24];
    Pack128_3 o_weight[1152];
    Pack128_16 o_bias[24];
    int32_t attn_scalars[3], ln_scalars[7], ln_lnw[192];
    int64_t ln_lnb[192];
    int32_t ln_rsqrt_table[128];
    int32_t qq_scalars[4];
    int8_t qq_table[64];
    int32_t kq_scalars[4];
    int8_t kq_table[64];
    int32_t vq_scalars[4];
    int8_t vq_table[64];
    int32_t aq_scalars[4];
    int8_t aq_table[64];
    int32_t softmax_scalars[14];
    uint16_t softmax_exp_table[32];
    uint8_t softmax_recip_table_one[64];
    int8_t softmax_recip_table_two[64];
};
struct MlpLayerWeights {
    Pack128_3 m1_weight[4608];
    Pack128_16 m1_bias[96];
    Pack128_3 m2_weight[4608];
    Pack128_16 m2_bias[24];
    int32_t mlp_scalars[2], ln_scalars[7], ln_lnw[192];
    int64_t ln_lnb[192];
    int32_t ln_rsqrt_table[128], ge_scalars[4];
    uint8_t ge_table[64];
};
struct BlockLayerWeights {
    AttnLayerWeights attn_weights;
    MlpLayerWeights mlp_weights;
};
static_assert(offsetof(MlpLayerWeights, ln_lnb) == 150184,
              "MlpLayerWeights must retain four-byte internal padding");
static_assert(offsetof(MlpLayerWeights, ge_table) + 64 == 152312,
              "MlpLayerWeights must retain eight-byte tail padding");


static void die(const char* s) {
    std::fprintf(stderr, "ERROR: %s\n", s);
    std::exit(2);
}

template<class T>
static void rd(FILE* f, T* p, size_t n, const char* what) {
    if (std::fread(p, sizeof(T), n, f) != n) {
        std::fprintf(stderr, "short read: %s\n", what);
        std::exit(3);
    }
}

template<size_t N>
static void rd_pack3(FILE* f, Pack128_3 (&dst)[N],
                     size_t nvals, const char* what) {
    if (nvals % 32 || nvals / 32 != N) die("pack3 count mismatch");

    std::vector<int8_t> v(nvals);
    rd(f, v.data(), nvals, what);

    for (size_t p = 0; p < N; ++p) {
        dst[p].d = 0;
        for (int j = 0; j < 32; ++j) {
            int value = v[p * 32 + j];
            if (value < -4 || value > 3) die("weight outside signed W3 range");
            dst[p].d |= static_cast<unsigned __int128>(value & 7) << (3 * j);
        }
    }
}

template<size_t N>
static void rd_pack16(FILE* f, Pack128_16 (&dst)[N],
                      size_t nvals, const char* what) {
    if (nvals % 8 || nvals / 8 != N) die("pack16 count mismatch");

    std::vector<int16_t> v(nvals);
    rd(f, v.data(), nvals, what);

    for (size_t p = 0; p < N; ++p) {
        dst[p].d = 0;
        for (int j = 0; j < 8; ++j) {
            dst[p].d |= static_cast<unsigned __int128>(static_cast<uint16_t>(v[p * 8 + j])) << (16 * j);
        }
    }
}

int main(int argc, char** argv) {
    if (argc != 3) {
        std::fprintf(stderr, "usage: %s fields.bin weights.bin\n", argv[0]);
        return 1;
    }

    std::printf("sizeof(Pack128_3)         = %zu\n", sizeof(Pack128_3));
    std::printf("sizeof(Pack128_16)        = %zu\n", sizeof(Pack128_16));
    std::printf("sizeof(AttnLayerWeights)  = %zu\n", sizeof(AttnLayerWeights));
    std::printf("sizeof(MlpLayerWeights)   = %zu\n", sizeof(MlpLayerWeights));
    std::printf("sizeof(BlockLayerWeights) = %zu\n", sizeof(BlockLayerWeights));

    if (sizeof(Pack128_3) != 16 ||
        sizeof(Pack128_16) != 16 ||
        sizeof(AttnLayerWeights) != 78688 ||
        sizeof(MlpLayerWeights) != 152320 ||
        sizeof(BlockLayerWeights) != 231008) {
        die("ABI differs from audited layout");
    }

    FILE* fi = std::fopen(argv[1], "rb");
    if (!fi) die("cannot open fields.bin");

    const uint16_t endian_test = 1;
    if (*reinterpret_cast<const uint8_t*>(&endian_test) != 1) die("little-endian host required");
    BlockLayerWeights L[12];
    std::memset(L, 0, sizeof(L));

    for (int b = 0; b < 12; ++b) {
        auto& a = L[b].attn_weights;
        auto& m = L[b].mlp_weights;

        rd_pack3(fi, a.q_weight, 192 * 192, "q_weight");
        rd_pack3(fi, a.k_weight, 192 * 192, "k_weight");
        rd_pack3(fi, a.v_weight, 192 * 192, "v_weight");

        rd_pack16(fi, a.q_bias, 192, "q_bias");
        rd_pack16(fi, a.k_bias, 192, "k_bias");
        rd_pack16(fi, a.v_bias, 192, "v_bias");

        rd_pack3(fi, a.o_weight, 192 * 192, "o_weight");
        rd_pack16(fi, a.o_bias, 192, "o_bias");

        rd(fi, a.attn_scalars, 3, "attn_scalars");
        rd(fi, a.ln_scalars, 7, "attn_ln_scalars");
        rd(fi, a.ln_lnw, 192, "attn_lnw");
        rd(fi, a.ln_lnb, 192, "attn_lnb");
        rd(fi, a.ln_rsqrt_table, 128, "attn_rsqrt");

        rd(fi, a.qq_scalars, 4, "qq_scalars");
        rd(fi, a.qq_table, 64, "qq_table");
        rd(fi, a.kq_scalars, 4, "kq_scalars");
        rd(fi, a.kq_table, 64, "kq_table");
        rd(fi, a.vq_scalars, 4, "vq_scalars");
        rd(fi, a.vq_table, 64, "vq_table");
        rd(fi, a.aq_scalars, 4, "aq_scalars");
        rd(fi, a.aq_table, 64, "aq_table");

        rd(fi, a.softmax_scalars, 14, "softmax_scalars");
        rd(fi, a.softmax_exp_table, 32, "softmax_exp");
        rd(fi, a.softmax_recip_table_one, 64, "softmax_recip1");
        rd(fi, a.softmax_recip_table_two, 64, "softmax_recip2");

        rd_pack3(fi, m.m1_weight, 768 * 192, "m1_weight");
        rd_pack16(fi, m.m1_bias, 768, "m1_bias");
        rd_pack3(fi, m.m2_weight, 192 * 768, "m2_weight");
        rd_pack16(fi, m.m2_bias, 192, "m2_bias");

        rd(fi, m.mlp_scalars, 2, "mlp_scalars");
        rd(fi, m.ln_scalars, 7, "mlp_ln_scalars");
        rd(fi, m.ln_lnw, 192, "mlp_lnw");
        rd(fi, m.ln_lnb, 192, "mlp_lnb");
        rd(fi, m.ln_rsqrt_table, 128, "mlp_rsqrt");
        rd(fi, m.ge_scalars, 4, "ge_scalars");
        rd(fi, m.ge_table, 64, "ge_table");
    }

    if (std::fgetc(fi) != EOF) die("fields.bin has trailing bytes");
    std::fclose(fi);

    FILE* fo = std::fopen(argv[2], "wb");
    if (!fo) die("cannot create weights.bin");

    if (std::fwrite(L, sizeof(BlockLayerWeights), 12, fo) != 12)
        die("short write");

    std::fclose(fo);

    std::printf("wrote %zu bytes\n", sizeof(BlockLayerWeights) * 12);
    return 0;
}

