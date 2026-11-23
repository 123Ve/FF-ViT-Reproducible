#ifndef M_SAMPLER_H
#define M_SAMPLER_H
#include "monitor.h"
typedef struct {
    m_shared *shared;m_io io;m_status status;
    uint64_t fresh[M_RAILS],next_scan,next_temperature,t0,t1,published_tick;
    uint32_t command_seq,diagnostic_frozen;
    int (*temperature)(uint32_t *,int32_t *);
} m_sampler;
int m_sampler_init(m_sampler *,m_shared *,m_io,unsigned,uint64_t,int (*)(uint32_t *,int32_t *));
void m_sampler_step(m_sampler *);
int m_hardware_init(m_io *);
int m_temperature_read(uint32_t *,int32_t *);
#endif
