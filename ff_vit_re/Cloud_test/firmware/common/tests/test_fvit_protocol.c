#include "fvit_protocol.h"

#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#define CHECK(condition) do { if (!(condition)) return __LINE__; } while (0)

static int hex_digit(char digit)
{
    if (digit >= '0' && digit <= '9') return digit - '0';
    if (digit >= 'a' && digit <= 'f') return digit - 'a' + 10;
    if (digit >= 'A' && digit <= 'F') return digit - 'A' + 10;
    return -1;
}

static int parse_hex_header(const char *hex, uint8_t bytes[FVIT_HEADER_SIZE])
{
    size_t index;
    if (strlen(hex) != FVIT_HEADER_SIZE * 2u) return -1;
    for (index = 0; index < FVIT_HEADER_SIZE; ++index) {
        int upper = hex_digit(hex[index * 2u]);
        int lower = hex_digit(hex[index * 2u + 1u]);
        if (upper < 0 || lower < 0) return -1;
        bytes[index] = (uint8_t)((upper << 4) | lower);
    }
    return 0;
}

static int selftest(void)
{
    static const uint8_t kinds[] = {1u, 2u, 3u, 4u, 5u, 6u, 7u, 8u, 255u};
    static const uint8_t expected[FVIT_HEADER_SIZE] = {
        0x46u, 0x56u, 0x49u, 0x54u, 1u, 5u, 0u, 0u,
        1u, 2u, 3u, 4u, 0u, 0u, 0u, 17u,
        0u, 2u, 76u, 0u
    };
    fvit_header_t header = {5u, UINT32_C(0x01020304), 17u, 150528u};
    fvit_header_t decoded = {0u, 0u, 0u, 0u};
    uint8_t wire[FVIT_HEADER_SIZE];
    size_t index;
    unsigned int kind;

    CHECK(fvit_header_encode(NULL, &header) == FVIT_ERR_ARGUMENT);
    CHECK(fvit_header_encode(wire, NULL) == FVIT_ERR_ARGUMENT);
    CHECK(fvit_header_decode(NULL, wire) == FVIT_ERR_ARGUMENT);
    CHECK(fvit_header_decode(&decoded, NULL) == FVIT_ERR_ARGUMENT);

    for (kind = 0u; kind < 256u; ++kind) {
        int valid = (kind >= 1u && kind <= 8u) || kind == 255u;
        CHECK(fvit_kind_is_valid((uint8_t)kind) == valid);
    }
    for (index = 0; index < sizeof(kinds) / sizeof(kinds[0]); ++index) {
        header.kind = kinds[index];
        CHECK(fvit_header_encode(wire, &header) == FVIT_OK);
        CHECK(wire[5] == kinds[index]);
        CHECK(wire[6] == 0u && wire[7] == 0u);
        CHECK(fvit_header_decode(&decoded, wire) == FVIT_OK);
        CHECK(decoded.kind == kinds[index]);
        CHECK(decoded.request_id == header.request_id);
        CHECK(decoded.metadata_len == header.metadata_len);
        CHECK(decoded.payload_len == header.payload_len);
    }

    header.kind = 5u;
    CHECK(fvit_header_encode(wire, &header) == FVIT_OK);
    CHECK(memcmp(wire, expected, sizeof(expected)) == 0);

    wire[0] = 0x58u;
    CHECK(fvit_header_decode(&decoded, wire) == FVIT_ERR_MAGIC);
    wire[0] = 0x46u;
    wire[4] = 2u;
    CHECK(fvit_header_decode(&decoded, wire) == FVIT_ERR_VERSION);
    wire[4] = 1u;
    wire[6] = 1u;
    CHECK(fvit_header_decode(&decoded, wire) == FVIT_ERR_ARGUMENT);
    wire[6] = 0u;
    wire[7] = 1u;
    CHECK(fvit_header_decode(&decoded, wire) == FVIT_ERR_ARGUMENT);
    wire[7] = 0u;
    wire[5] = 9u;
    CHECK(fvit_header_decode(&decoded, wire) == FVIT_ERR_KIND);
    wire[5] = 5u;
    header.kind = 9u;
    CHECK(fvit_header_encode(wire, &header) == FVIT_ERR_KIND);

    header.kind = 5u;
    header.request_id = UINT32_MAX;
    header.metadata_len = FVIT_MAX_METADATA_BYTES;
    header.payload_len = FVIT_MAX_PAYLOAD_BYTES;
    CHECK(fvit_header_encode(wire, &header) == FVIT_OK);
    CHECK(fvit_header_decode(&decoded, wire) == FVIT_OK);
    CHECK(decoded.request_id == UINT32_MAX);
    CHECK(decoded.metadata_len == FVIT_MAX_METADATA_BYTES);
    CHECK(decoded.payload_len == FVIT_MAX_PAYLOAD_BYTES);

    header.metadata_len = FVIT_MAX_METADATA_BYTES + 1u;
    CHECK(fvit_header_encode(wire, &header) == FVIT_ERR_SIZE);
    wire[15] = 1u;
    CHECK(fvit_header_decode(&decoded, wire) == FVIT_ERR_SIZE);
    header.metadata_len = 0u;
    header.payload_len = FVIT_MAX_PAYLOAD_BYTES + 1u;
    CHECK(fvit_header_encode(wire, &header) == FVIT_ERR_SIZE);
    CHECK(fvit_header_encode(wire, &(fvit_header_t){5u, 0u, 0u, 0u}) == FVIT_OK);
    wire[17] = 64u;
    wire[19] = 1u;
    CHECK(fvit_header_decode(&decoded, wire) == FVIT_ERR_SIZE);
    return 0;
}

int main(int argc, char **argv)
{
    fvit_header_t header;
    uint8_t wire[FVIT_HEADER_SIZE];
    size_t index;
    int result;

    if (argc == 2 && strcmp(argv[1], "encode") == 0) {
        header = (fvit_header_t){5u, UINT32_C(0x01020304), 17u, 150528u};
        if (fvit_header_encode(wire, &header) != FVIT_OK) return 1;
        for (index = 0; index < FVIT_HEADER_SIZE; ++index) printf("%02x", (unsigned int)wire[index]);
        putchar('\n');
        return 0;
    }
    if (argc == 3 && strcmp(argv[1], "decode") == 0) {
        if (parse_hex_header(argv[2], wire) != 0) return 2;
        if (fvit_header_decode(&header, wire) != FVIT_OK) return 1;
        printf("%u,%" PRIu32 ",%" PRIu32 ",%" PRIu32 "\n",
               (unsigned int)header.kind, header.request_id,
               header.metadata_len, header.payload_len);
        return 0;
    }
    if (argc == 2 && strcmp(argv[1], "selftest") == 0) {
        result = selftest();
        if (result != 0) fprintf(stderr, "selftest failed at line %d\n", result);
        return result == 0 ? 0 : 1;
    }
    return 2;
}
