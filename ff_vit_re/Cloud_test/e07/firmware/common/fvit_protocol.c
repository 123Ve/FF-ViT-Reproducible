#include "fvit_protocol.h"

static void encode_u32(uint8_t *out, uint32_t value)
{
    out[0] = (uint8_t)(value >> 24);
    out[1] = (uint8_t)(value >> 16);
    out[2] = (uint8_t)(value >> 8);
    out[3] = (uint8_t)value;
}

static uint32_t decode_u32(const uint8_t *in)
{
    return ((uint32_t)in[0] << 24)
         | ((uint32_t)in[1] << 16)
         | ((uint32_t)in[2] << 8)
         | (uint32_t)in[3];
}

int fvit_kind_is_valid(uint8_t kind)
{
    return (kind >= 1u && kind <= 8u) || kind == 255u;
}

int fvit_header_encode(uint8_t out[FVIT_HEADER_SIZE], const fvit_header_t *header)
{
    if (out == 0 || header == 0) return FVIT_ERR_ARGUMENT;
    if (!fvit_kind_is_valid(header->kind)) return FVIT_ERR_KIND;
    if (header->metadata_len > FVIT_MAX_METADATA_BYTES
            || header->payload_len > FVIT_MAX_PAYLOAD_BYTES) return FVIT_ERR_SIZE;

    out[0] = 0x46u;
    out[1] = 0x56u;
    out[2] = 0x49u;
    out[3] = 0x54u;
    out[4] = 1u;
    out[5] = header->kind;
    out[6] = 0u;
    out[7] = 0u;
    encode_u32(out + 8, header->request_id);
    encode_u32(out + 12, header->metadata_len);
    encode_u32(out + 16, header->payload_len);
    return FVIT_OK;
}

int fvit_header_decode(fvit_header_t *out, const uint8_t in[FVIT_HEADER_SIZE])
{
    fvit_header_t decoded;
    if (out == 0 || in == 0) return FVIT_ERR_ARGUMENT;
    if (in[0] != 0x46u || in[1] != 0x56u || in[2] != 0x49u || in[3] != 0x54u)
        return FVIT_ERR_MAGIC;
    if (in[4] != 1u) return FVIT_ERR_VERSION;
    if (in[6] != 0u || in[7] != 0u) return FVIT_ERR_ARGUMENT;
    if (!fvit_kind_is_valid(in[5])) return FVIT_ERR_KIND;

    decoded.kind = in[5];
    decoded.request_id = decode_u32(in + 8);
    decoded.metadata_len = decode_u32(in + 12);
    decoded.payload_len = decode_u32(in + 16);
    if (decoded.metadata_len > FVIT_MAX_METADATA_BYTES
            || decoded.payload_len > FVIT_MAX_PAYLOAD_BYTES) return FVIT_ERR_SIZE;
    *out = decoded;
    return FVIT_OK;
}
