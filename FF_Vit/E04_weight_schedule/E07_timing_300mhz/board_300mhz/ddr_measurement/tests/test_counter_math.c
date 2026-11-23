/* Wrong modulo-wrap arithmetic must fail this native test. */
#include <assert.h>
#include "counter_math.h"
int main(void) {
    assert(counter_delta(0xfffffff0u, 0x20u) == 48u);
    assert(counter_delta(3u, 100u) == 97u);
    return 0;
}
