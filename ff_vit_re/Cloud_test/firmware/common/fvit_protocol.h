#ifndef FVIT_PROTOCOL_H
#define FVIT_PROTOCOL_H

#include <stdint.h>

#define FVIT_HEADER_SIZE 20u
#define FVIT_MAX_METADATA_BYTES 65536u
#define FVIT_MAX_PAYLOAD_BYTES 4194304u

typedef struct {
    uint8_t kind;
    uint32_t request_id;
    uint32_t metadata_len;
    uint32_t payload_len;
} fvit_header_t;

enum {
    FVIT_OK = 0,
    FVIT_ERR_ARGUMENT = -1,
    FVIT_ERR_MAGIC = -2,
    FVIT_ERR_VERSION = -3,
    FVIT_ERR_KIND = -4,
    FVIT_ERR_SIZE = -5
};

int fvit_header_encode(uint8_t out[FVIT_HEADER_SIZE], const fvit_header_t *header);
int fvit_header_decode(fvit_header_t *out, const uint8_t in[FVIT_HEADER_SIZE]);
int fvit_kind_is_valid(uint8_t kind);

#endif
