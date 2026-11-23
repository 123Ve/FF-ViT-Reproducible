#include "bounded_i2c.h"
/* Cadence PS I2C register map/bits from the installed xiicps_hw.h. Only 1..3
   byte transfers are needed here, below FIFO depth, without repeated START. */
enum {
    I2C_CR=0, I2C_SR=4, I2C_ADDRESS=8, I2C_DATA=12,
    I2C_ISR=16, I2C_SIZE=20, I2C_IDR=40,
    I2C_CR_RECEIVE=0x01, I2C_CR_MASTER=0x02, I2C_CR_7BIT=0x04,
    I2C_CR_ACK=0x08, I2C_CR_CLEAR_FIFO=0x40, I2C_CR_DIVIDERS=0xff00,
    I2C_SR_RX_DATA_VALID=0x20, I2C_SR_BUS_ACTIVE=0x100,
    I2C_IRQ_COMPLETE=0x01, I2C_IRQ_NACK=0x04, I2C_IRQ_TIMEOUT=0x08,
    I2C_IRQ_RX_OVERFLOW=0x20, I2C_IRQ_TX_OVERFLOW=0x40,
    I2C_IRQ_RX_UNDERFLOW=0x80, I2C_IRQ_ARBITRATION_LOST=0x200,
    I2C_IRQ_ALL=0x2ff,
    I2C_IRQ_ERRORS=I2C_IRQ_NACK|I2C_IRQ_TIMEOUT|I2C_IRQ_RX_OVERFLOW|
                   I2C_IRQ_TX_OVERFLOW|I2C_IRQ_RX_UNDERFLOW|I2C_IRQ_ARBITRATION_LOST
};

int m_i2c_transfer(m_register_io *io, uint8_t address, uint8_t *data,
                   unsigned count, int receive) {
    if (!io || !data || !count || count>3 || address>127 || io->hz<500)
        return -1;

    const uint64_t limit=io->hz/500; /* Separate 2ms idle and transfer limits. */
    uint64_t begin=io->ticks(io->ctx);
    while (io->read(io->ctx,I2C_SR)&I2C_SR_BUS_ACTIVE) {
        if (io->ticks(io->ctx)-begin>=limit)
            return -1;
    }

    uint32_t control=io->read(io->ctx,I2C_CR)&I2C_CR_DIVIDERS;
    control|=I2C_CR_CLEAR_FIFO|I2C_CR_ACK|I2C_CR_7BIT|I2C_CR_MASTER;
    if (receive)
        control|=I2C_CR_RECEIVE;
    io->write(io->ctx,I2C_CR,control); /* No HOLD; every transfer sends STOP. */
    io->write(io->ctx,I2C_IDR,I2C_IRQ_ALL);
    io->write(io->ctx,I2C_ISR,I2C_IRQ_ALL);
    if (receive) {
        io->write(io->ctx,I2C_SIZE,count);
    } else {
        for (unsigned n=0;n<count;n++)
            io->write(io->ctx,I2C_DATA,data[n]);
    }
    io->write(io->ctx,I2C_ADDRESS,address);

    begin=io->ticks(io->ctx);
    unsigned used=0;
    for (;;) {
        uint32_t flags=io->read(io->ctx,I2C_ISR);
        if (flags&I2C_IRQ_ERRORS)
            break;
        if (receive && used<count && (io->read(io->ctx,I2C_SR)&I2C_SR_RX_DATA_VALID))
            data[used++]=(uint8_t)io->read(io->ctx,I2C_DATA);
        if ((flags&I2C_IRQ_COMPLETE) && (!receive || used==count) &&
                !(io->read(io->ctx,I2C_SR)&I2C_SR_BUS_ACTIVE))
            return 0;
        if (io->ticks(io->ctx)-begin>=limit)
            break;
    }
    io->write(io->ctx,I2C_CR,control); /* Discard the incomplete FIFO. */
    io->write(io->ctx,I2C_ISR,I2C_IRQ_ALL);
    return -1;
}
