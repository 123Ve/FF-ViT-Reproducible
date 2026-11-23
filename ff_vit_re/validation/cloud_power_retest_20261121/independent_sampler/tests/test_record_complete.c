/* Actual sampler with register I/O from the retained native sensor fixture. */
#define main retained_conversion_fixture_main
#include "test_first_conversion.c"
#undef main

int main(void) {
    fake f;init(&f);f.tick=1000000;
    m_shared *p=calloc(1,sizeof(*p));assert(p);
    m_service service;m_sampler sampler;
    m_service_init(&service,p,1000000,0,1);
    assert(!m_sampler_init(&sampler,p,io_for(&f),1,1000000,temperature));
    uint64_t base=f.tick;
    for(unsigned rail=0;rail<18;rail++)f.regs[rail][6]=8;
    for(unsigned n=0;n<3;n++) {
        unsigned rail=(unsigned[]){6,7,15}[n];
        f.regs[rail][1]=65534;f.regs[rail][4]=65534;f.regs[rail][3]=0;
    }
    f.tick=base+120000;m_sampler_step(&sampler);
    /* CVRF proves all ADCs updated, including negative-valued rails. */
    assert(sampler.status.observed_mask==262143);
    assert(sampler.status.conversion_ready==229183);
    if(E07_PROFILE_RAILS==18) {
        assert(sampler.status.faults==M_FAULT_SENSOR);
        assert(sampler.status.invalid_samples==3&&sampler.diagnostic_frozen);
    } else {
        assert(!sampler.status.faults&&!sampler.status.invalid_samples&&!sampler.diagnostic_frozen);
        for(unsigned scan=1;scan<=55;scan++) {
            /* Every other software scan observes a real conversion. */
            if(scan%2==0)for(unsigned rail=0;rail<18;rail++)f.regs[rail][6]=8;
            f.tick=base+120000+scan*20000;m_sampler_step(&sampler);
        }
        service.clock_checks=service.heartbeat_advances=3;
        assert(m_service_ready(&service,f.tick));
        m_rail_record rows[18];assert(!m_latest_read(p,rows));
        assert(rows[15].shunt==65534&&rows[15].current==65534&&rows[15].power==0);
        assert(rows[15].flags==M_NEGATIVE&&rows[15].power_uW==INT64_MIN);
        assert(sampler.status.included_negative_samples>0);
        assert(sampler.status.excluded_negative_samples>0);
        /* A genuine sensor error remains fatal even on an excluded rail. */
        for(unsigned rail=0;rail<18;rail++)f.regs[rail][6]=8;
        f.regs[15][6]=12;f.tick+=20000;m_sampler_step(&sampler);
        assert(sampler.status.faults==M_FAULT_SENSOR&&sampler.status.invalid_samples==1);
        assert(sampler.diagnostic_frozen&&!m_latest_read(p,rows));
        assert(rows[15].flags==(M_NEGATIVE|M_FRESH|M_OVERFLOW));
    }
    free(p);puts("ADC_OBSERVATION_NEGATIVE_QUALITY_AND_REAL_FAULT_OK");return 0;
}
