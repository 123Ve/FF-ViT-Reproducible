/* The narrow I/O fixture provides real sampler time, not fabricated CVRF flags. */
#define main retained_first_conversion_main
#include "test_first_conversion.c"
#undef main
int main(void) {
    fake f;init(&f);f.tick=1000000;
    m_shared *p=calloc(1,sizeof(*p));assert(p);m_service service;m_sampler sampler;
    m_service_init(&service,p,1000000,0,1);
    assert(!m_sampler_init(&sampler,p,io_for(&f),1,1000000,temperature));
    for(unsigned rail=0;rail<18;rail++)f.regs[rail][6]=8;
    f.tick+=40000;m_sampler_step(&sampler);
    uint64_t first=sampler.status.ping_tick,heartbeat=sampler.status.heartbeat;
    uint32_t sequence=sampler.status.ping_seq;
    f.tick+=20000;m_sampler_step(&sampler);
    assert(sampler.status.ping_seq==sequence);
    assert(sampler.status.ping_tick==first); /* old code overwrote this on every iteration */
    assert(sampler.status.heartbeat>heartbeat);
    ++p->control.ping_seq;f.tick+=20000;m_sampler_step(&sampler);
    assert(sampler.status.ping_seq==sequence+1&&sampler.status.ping_tick>first);
    first=sampler.status.ping_tick;f.tick+=20000;m_sampler_step(&sampler);
    assert(sampler.status.ping_tick==first&&sampler.status.heartbeat>first);
    free(p);puts("FIRST_PING_OBSERVATION_LATCHED_HEARTBEAT_STILL_ADVANCES");return 0;
}
