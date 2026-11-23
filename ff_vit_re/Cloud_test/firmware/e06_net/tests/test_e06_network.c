#include "e06_network.h"
#include "fvit_protocol.h"
#include "fake_lwip.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define INPUT_BYTES 602112u
void fake_lwip_reset(void); struct tcp_pcb *fake_last_pcb(void); size_t fake_pcb_count(void);
const unsigned char *fake_wire(void); size_t fake_wire_size(void); void fake_wire_clear(void);
unsigned long fake_recved_bytes(void);
void fake_fail_write(int); void fake_fail_output(int); void fake_fail_close(int);
int fake_post_invalidation_calls(void); int fake_inference_calls(void); int fake_telemetry_calls(void);
uint32_t fake_configured_ip(void); uint32_t fake_configured_mask(void); uint32_t fake_configured_gateway(void); uint32_t fake_connected_ip(void);
err_t fake_connect_success(void); void fake_remote_error(err_t); void fake_ack_all(void);
static struct tcp_pcb *connection;
static void header_at(size_t offset, fvit_header_t *h) { assert(fake_wire_size() >= offset + FVIT_HEADER_SIZE); assert(fvit_header_decode(h, fake_wire() + offset) == FVIT_OK); }
static size_t frame_size(size_t offset) { fvit_header_t h; header_at(offset, &h); return FVIT_HEADER_SIZE + h.metadata_len + h.payload_len; }
static void expect_kind(size_t offset, uint8_t kind, uint32_t id) { fvit_header_t h; header_at(offset, &h); assert(h.kind == kind && h.request_id == id); }
static void start_and_connect(void) {
    fake_lwip_reset(); assert(e06_network_start() == 0); connection = fake_last_pcb(); assert(connection != NULL);
    assert(fake_configured_ip() == 0x020aa8c0u && fake_configured_mask() == 0x00ffffffu);
    assert(fake_configured_gateway() == 0x010aa8c0u && fake_connected_ip() == 0x010aa8c0u);
    assert(connection->remote_port == 5001 && fake_wire_size() == 0u);
    assert(fake_connect_success() == ERR_OK); expect_kind(0, 5, 0); assert(frame_size(0) == fake_wire_size());
    assert(strstr((const char *)fake_wire() + FVIT_HEADER_SIZE, "E06_PHYSICAL") != NULL);
    assert(connection->recv_cb && connection->err_cb && connection->sent_cb);
}
static void feed(const unsigned char *data, size_t size, size_t chunk, err_t expected) {
    size_t at = 0; err_t status = ERR_OK;
    while (at < size && status == ERR_OK) {
        struct pbuf nodes[3]; size_t count = 0, group = size - at, local = 0;
        if (group > chunk * 3u) group = chunk * 3u;
        while (local < group) { size_t n = group - local; if (n > chunk) n = chunk;
            nodes[count].payload = (void *)(data + at + local); nodes[count].len = (u16_t)n;
            nodes[count].tot_len = (u16_t)(group - local); nodes[count].next = NULL;
            if (count) nodes[count - 1].next = &nodes[count];
            ++count; local += n; }
        status = connection->recv_cb(connection->callback_arg, connection, nodes, ERR_OK); at += group;
    }
    assert(status == expected);
}
static size_t command(unsigned char *out, uint32_t id, const char *name, const char *arguments) {
    char metadata[256]; fvit_header_t h; int n = snprintf(metadata, sizeof(metadata), "{\"arguments\":%s,\"name\":\"%s\"}", arguments, name);
    assert(n > 0 && (size_t)n < sizeof(metadata)); h.kind = 7; h.request_id = id; h.metadata_len = (uint32_t)n; h.payload_len = 0;
    assert(fvit_header_encode(out, &h) == FVIT_OK); memcpy(out + FVIT_HEADER_SIZE, metadata, (size_t)n); return FVIT_HEADER_SIZE + (size_t)n;
}
static size_t send_command(uint32_t id, const char *name, const char *arguments, size_t chunk) {
    unsigned char frame[300]; size_t n = command(frame, id, name, arguments); feed(frame, n, chunk, ERR_OK);
    return n;
}
static void drain_bulk(void) { size_t old; do { old = fake_wire_size(); fake_ack_all(); } while (fake_wire_size() != old); }
static void test_commands_and_fragmentation(void) {
    size_t off, received; int before; fvit_header_t h;
    start_and_connect(); fake_wire_clear();
    received = send_command(1, "health", "{}", 1);
    assert(fake_recved_bytes() == received);
    expect_kind(0, 4, 1); assert(fake_inference_calls() == 0);
    fake_ack_all(); fake_wire_clear(); send_command(2, "telemetry", "{}", 7); expect_kind(0, 6, 2); assert(fake_telemetry_calls() == 1);
    fake_ack_all(); fake_wire_clear(); send_command(3, "run_once", "{}", 20); expect_kind(0, 8, 3); off = frame_size(0); expect_kind(off, 6, 3); assert(fake_inference_calls() == 1);
    fake_ack_all(); fake_wire_clear(); before = fake_inference_calls(); send_command(4, "repeat_latency", "{\"count\":3}", 2); expect_kind(0, 4, 4); assert(fake_inference_calls() == before + 3);
    fake_ack_all(); fake_wire_clear(); before = fake_inference_calls(); send_command(5, "compact_result", "{}", 3); expect_kind(0, 2, 5); assert(fake_inference_calls() == before + 1);
    fake_ack_all(); fake_wire_clear(); before = fake_inference_calls(); send_command(6, "full_payload", "{}", 5); drain_bulk();
    expect_kind(0, 1, 6); header_at(0, &h); assert(h.payload_len == INPUT_BYTES); assert(frame_size(0) == fake_wire_size());
    assert(fake_wire()[FVIT_HEADER_SIZE + h.metadata_len] == 0u);
    assert(fake_wire()[fake_wire_size() - 1u] == (unsigned char)((INPUT_BYTES - 1u) & 0xffu));
    assert(fake_inference_calls() == before && fake_post_invalidation_calls() == 0);
}
static void test_errors_and_abort_lifetime(void) {
    unsigned char frame[300]; size_t n; int before; fvit_header_t header;
    start_and_connect(); fake_wire_clear(); before = fake_inference_calls();
    send_command(10, "unknown", "{}", 1); expect_kind(0, 255, 10); assert(fake_inference_calls() == before);
    fake_ack_all(); fake_wire_clear(); send_command(11, "repeat_latency", "{\"count\":0}", 2); expect_kind(0, 255, 11);
    fake_ack_all(); fake_wire_clear(); send_command(12, "repeat_latency", "{\"count\":17}", 2); expect_kind(0, 255, 12);
    fake_ack_all(); fake_wire_clear();
    header.kind = 7u; header.request_id = 13u; header.metadata_len = 8u; header.payload_len = 0u;
    assert(fvit_header_encode(frame, &header) == FVIT_OK); memcpy(frame + FVIT_HEADER_SIZE, "not-json", 8u);
    feed(frame, FVIT_HEADER_SIZE + 8u, 1u, ERR_OK); expect_kind(0, 255, 13);
    fake_ack_all(); fake_wire_clear();
    memset(frame, 0, FVIT_HEADER_SIZE); memcpy(frame, "BAD!", 4); frame[4] = 1; frame[5] = 7;
    feed(frame, FVIT_HEADER_SIZE, 4, ERR_ABRT); assert(connection->aborted && fake_post_invalidation_calls() == 0);
    start_and_connect(); fake_ack_all(); fake_wire_clear();
    memset(frame, 0, FVIT_HEADER_SIZE); memcpy(frame, "FVIT", 4); frame[4] = 1; frame[5] = 7;
    frame[12] = 0x00; frame[13] = 0x01; frame[14] = 0x00; frame[15] = 0x01;
    feed(frame, FVIT_HEADER_SIZE, FVIT_HEADER_SIZE, ERR_ABRT);
    assert(connection->aborted && fake_post_invalidation_calls() == 0);
    start_and_connect(); fake_ack_all(); fake_wire_clear(); fake_fail_write(1); n = command(frame, 20, "health", "{}");
    feed(frame, n, n, ERR_ABRT); assert(connection->aborted && fake_post_invalidation_calls() == 0);
    start_and_connect(); fake_ack_all(); fake_wire_clear(); fake_fail_output(1); n = command(frame, 21, "health", "{}");
    feed(frame, n, n, ERR_ABRT); assert(connection->aborted && fake_post_invalidation_calls() == 0);
}
static void test_close_error_and_reconnect(void) {
    size_t old_count; start_and_connect(); fake_wire_clear();
    assert(connection->recv_cb(connection->callback_arg, connection, NULL, ERR_OK) == ERR_OK);
    assert(connection->closed && fake_post_invalidation_calls() == 0); old_count = fake_pcb_count();
    e06_network_poll(); e06_network_poll(); e06_network_poll(); e06_network_poll();
    assert(fake_pcb_count() > old_count); connection = fake_last_pcb(); assert(fake_connect_success() == ERR_OK);
    expect_kind(0, 5, 0); assert(frame_size(0) == fake_wire_size());
    fake_remote_error(ERR_MEM); assert(fake_post_invalidation_calls() == 0);

    start_and_connect(); fake_wire_clear(); fake_fail_close(1);
    assert(connection->recv_cb(connection->callback_arg, connection, NULL, ERR_OK) == ERR_ABRT);
    assert(connection->aborted && fake_post_invalidation_calls() == 0); old_count = fake_pcb_count();
    e06_network_poll(); e06_network_poll(); e06_network_poll(); e06_network_poll();
    assert(fake_pcb_count() > old_count); connection = fake_last_pcb(); assert(fake_connect_success() == ERR_OK);
    expect_kind(0, 5, 0); assert(frame_size(0) == fake_wire_size());
}
int main(void) { test_commands_and_fragmentation(); test_errors_and_abort_lifetime(); test_close_error_and_reconnect(); puts("E06 network tests passed"); return 0; }
