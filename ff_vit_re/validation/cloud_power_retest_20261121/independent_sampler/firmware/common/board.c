#include "monitor.h"
#ifdef E06_HOST_TEST
uint64_t m_test_ticks;
uint64_t m_ticks(void){return m_test_ticks++;}
uint64_t m_frequency(void){return 1000000;}
unsigned m_core_id(void){return 0;}
void m_map_shared(void){}
#else
#include "xil_mmu.h"
uint64_t m_ticks(void){uint64_t v;__asm__ volatile("isb; mrs %0, cntpct_el0":"=r"(v)::"memory");return v;}
uint64_t m_frequency(void){uint64_t v;__asm__ volatile("mrs %0, cntfrq_el0":"=r"(v));return v;}
unsigned m_core_id(void){uint64_t v;__asm__ volatile("mrs %0, mpidr_el1":"=r"(v));return (unsigned)(v&255);}
void m_map_shared(void){
    /* Each ELF owns separate translation tables. Do this before touching the
       reserved region. 2MiB blocks, normal noncacheable, shareable, XN. */
    for(uint64_t a=M_SHARED_BASE;a<M_SHARED_BASE+M_SHARED_BYTES;a+=0x200000)
        /* BSP EXECUTE_NEVER shifts an int by 53/54; use explicit 64-bit bits. */
        Xil_SetTlbAttributes(a,NORM_NONCACHE|INNER_SHAREABLE|(UINT64_C(1)<<53)|(UINT64_C(1)<<54));
    __asm__ volatile("dsb sy; isb":::"memory");
}
#endif
