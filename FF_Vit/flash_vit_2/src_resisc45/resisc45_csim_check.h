#ifndef RESISC45_CSIM_CHECK_H
#define RESISC45_CSIM_CHECK_H
#include <cstdio>
#include <cstdint>

// Simulation-only checks. Missing/truncated/trailing data is a hard failure.
static bool resisc45_compare(const char* actual, const char* expected, int count) {
    FILE* a = std::fopen(actual, "rb");
    FILE* e = std::fopen(expected, "rb");
    bool valid = a && e;
    int mismatches = 0;
    for (int i = 0; valid && i < count; ++i) {
        int32_t av, ev;
        if (std::fread(&av, sizeof(av), 1, a) != 1 ||
            std::fread(&ev, sizeof(ev), 1, e) != 1) {
            valid = false;
        } else if (av != ev) {
            ++mismatches;
        }
    }
    if (valid && (std::fgetc(a) != EOF || std::fgetc(e) != EOF ||
                  std::ferror(a) || std::ferror(e))) valid = false;
    if (a) std::fclose(a);
    if (e) std::fclose(e);
    std::printf("RESISC45_CHECK %s values=%d mismatches=%d valid=%d\n",
                actual, count, mismatches, valid ? 1 : 0);
    return valid && mismatches == 0;
}

static bool resisc45_check_all() {
    bool ok = resisc45_compare("hls_patch_out.bin", "ref_patch.bin", 37632);
    for (int i = 0; i < 12; ++i) {
        char actual[64], expected[64];
        std::snprintf(actual, sizeof(actual), "hls_block%d_out.bin", i);
        std::snprintf(expected, sizeof(expected), "ref_block%d_out.bin", i);
        ok = resisc45_compare(actual, expected, 37632) && ok;
    }
    ok = resisc45_compare("hls_head_input.bin", "ref_head_input.bin", 192) && ok;
    ok = resisc45_compare("hls_head_ln.bin", "ref_head_ln.bin", 192) && ok;
    ok = resisc45_compare("hls_logits.bin", "ref_logits.bin", 1000) && ok;
    return ok;
}
#endif
