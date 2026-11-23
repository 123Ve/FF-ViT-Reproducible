#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "frame_performance.h"

int main(int argc, char **argv) {
    if (argc != 4) return 2;
    uint64_t ns = 0, fps_milli = 0;
    if (!frame_performance(strtoull(argv[1], NULL, 10),
                           (uint32_t)strtoul(argv[2], NULL, 10),
                           (uint32_t)strtoul(argv[3], NULL, 10), &ns, &fps_milli)) {
        puts("INVALID");
        return 0;
    }
    printf("%llu,%llu\n", (unsigned long long)ns, (unsigned long long)fps_milli);
    return 0;
}
