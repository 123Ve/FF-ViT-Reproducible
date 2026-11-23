#ifndef BOUNDED_I2C_H
#define BOUNDED_I2C_H
#include <stdint.h>
typedef struct {
    void *ctx;uint32_t (*read)(void *,uint32_t);void (*write)(void *,uint32_t,uint32_t);
    uint64_t (*ticks)(void *);uint64_t hz;
} m_register_io;
int m_i2c_transfer(m_register_io *,uint8_t,uint8_t *,unsigned,int);
#endif
