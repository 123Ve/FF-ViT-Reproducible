#ifndef E06_STATUS_H
#define E06_STATUS_H
typedef enum {
    E06_OK = 0,
    E06_ERR_ARGUMENT = -1,
    E06_ERR_INIT = -2,
    E06_ERR_IO = -3,
    E06_ERR_DMA = -4,
    E06_ERR_TIMEOUT = -5,
    E06_ERR_MISMATCH = -6,
    E06_ERR_SENSOR = -7
} e06_status_t;
#endif
