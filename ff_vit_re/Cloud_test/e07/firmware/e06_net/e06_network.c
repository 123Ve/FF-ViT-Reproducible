#include "e06_network.h"
#include "net_config.h"
#include "e06_inference.h"
#include "e06_telemetry.h"
#include "fvit_protocol.h"
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#ifdef E06_HOST_TEST
#include "fake_lwip.h"
#define E06_NET_LOG(...) ((void)0)
#define E06_RECONNECT_POLLS 3u
#else
#include "lwip/init.h"
#include "lwip/ip_addr.h"
#include "lwip/priv/tcp_priv.h"
#include "lwip/tcp.h"
#include "netif/xadapter.h"
#include "xil_printf.h"
#include "xparameters.h"
#include "xiltimer.h"
#include "platform.h"
#include "e07_gem_tx.h"
#define E06_NET_LOG(...) xil_printf(__VA_ARGS__)
#define E06_RECONNECT_POLLS 100000u
#endif

#define E06_TX_FRAME_BYTES 2048u
#define E06_REPEAT_MAX 16u
#ifndef E07_BATCH_VERIFY
#define E07_BATCH_VERIFY 1
#endif
#define E07_TX_CHUNK_MAX 1460u

typedef struct {
    char name[64];
    uint32_t count;
    int has_count;
} e06_command_t;

typedef struct {
    struct tcp_pcb *pcb;
    uint8_t header_bytes[FVIT_HEADER_SIZE];
    size_t header_used;
    fvit_header_t header;
    char metadata[FVIT_MAX_METADATA_BYTES + 1u];
    size_t metadata_used;
    int header_ready;
    int connected;
    const uint8_t *bulk_data;
    size_t bulk_bytes;
    size_t bulk_offset;
    int bulk_active;
    uint64_t bulk_last_progress;
    uint64_t bulk_last_diagnostic;
    uint32_t bulk_mem_retries;
    uint32_t bulk_end_seq;
    uint32_t bulk_last_ack;
    uint32_t bulk_request_id;
    size_t payload_used;
    int payload_mismatch;
    uint64_t rx_start_ticks;
    uint64_t rx_end_ticks;
} e06_connection_t;

static uint64_t network_ticks(void) {
#ifdef E06_HOST_TEST
    static uint64_t ticks;
    return ++ticks;
#else
    XTime ticks;
    XTime_GetTime(&ticks);
    return (uint64_t)ticks;
#endif
}

static struct netif e06_netif;
#ifndef E06_HOST_TEST
static e07_gem_tx_service_t gem_tx_service;
#endif
static ip_addr_t collector_address;
static e06_connection_t connection;
static uint32_t completed_frames;
static uint32_t reconnect_polls;
static uint8_t tx_frame[E06_TX_FRAME_BYTES];

static void reset_parser(e06_connection_t *state)
{
    state->header_used = 0u;
    state->metadata_used = 0u;
    state->header_ready = 0;
    state->payload_used = 0u;
    state->payload_mismatch = 0;
    memset(&state->header, 0, sizeof(state->header));
}

static void release_state(e06_connection_t *state)
{
    state->pcb = NULL;
    state->connected = 0;
    state->bulk_data = NULL;
    state->bulk_bytes = 0u;
    state->bulk_offset = 0u;
    state->bulk_active = 0;
    reset_parser(state);
    reconnect_polls = E06_RECONNECT_POLLS;
}

static void detach_callbacks(struct tcp_pcb *pcb)
{
    tcp_arg(pcb, NULL);
    tcp_recv(pcb, NULL);
    tcp_sent(pcb, NULL);
    tcp_err(pcb, NULL);
}

static err_t abort_connection(e06_connection_t *state, const char *reason)
{
    struct tcp_pcb *pcb = state->pcb;
    E06_NET_LOG("NETWORK_ABORT=%s\r\n", reason);
    (void)reason;
    if (pcb == NULL) {
        release_state(state);
        return ERR_ABRT;
    }
    detach_callbacks(pcb);
    release_state(state);
    tcp_abort(pcb);
    return ERR_ABRT;
}

static err_t close_connection(e06_connection_t *state, const char *reason)
{
    struct tcp_pcb *pcb = state->pcb;
    err_t status;
    E06_NET_LOG("NETWORK_CLOSE=%s\r\n", reason);
    (void)reason;
    if (pcb == NULL) {
        release_state(state);
        return ERR_OK;
    }
    detach_callbacks(pcb);
    release_state(state);
    status = tcp_close(pcb);
    if (status == ERR_OK) return ERR_OK;
    E06_NET_LOG("NETWORK_CLOSE_ABORT=%d\r\n", (int)status);
    tcp_abort(pcb);
    return ERR_ABRT;
}

static err_t send_json(e06_connection_t *state, uint8_t kind,
                       uint32_t request_id, const char *json)
{
    fvit_header_t header;
    size_t metadata_bytes = strlen(json);
    size_t total = FVIT_HEADER_SIZE + metadata_bytes;
    err_t status;
    if (state->pcb == NULL || !state->connected || metadata_bytes > FVIT_MAX_METADATA_BYTES
            || total > sizeof(tx_frame))
        return abort_connection(state, "invalid transmit state");
    header.kind = kind;
    header.request_id = request_id;
    header.metadata_len = (uint32_t)metadata_bytes;
    header.payload_len = 0u;
    if (fvit_header_encode(tx_frame, &header) != FVIT_OK)
        return abort_connection(state, "header encode failed");
    memcpy(tx_frame + FVIT_HEADER_SIZE, json, metadata_bytes);
    status = tcp_write(state->pcb, tx_frame, (u16_t)total, TCP_WRITE_FLAG_COPY);
    if (status != ERR_OK) return abort_connection(state, "tcp_write failed");
    status = tcp_output(state->pcb);
    if (status != ERR_OK) return abort_connection(state, "tcp_output failed");
    return ERR_OK;
}

static err_t send_error(e06_connection_t *state, uint32_t request_id,
                        const char *code, const char *detail)
{
    char json[384];
    int written = snprintf(json, sizeof(json),
        "{\"code\":\"%s\",\"detail\":\"%s\",\"phase\":\"%s\"}",
        code, detail, E06_STAGE);
    if (written < 0 || (size_t)written >= sizeof(json))
        return abort_connection(state, "error response overflow");
    return send_json(state, 255u, request_id, json);
}

static const char *skip_space(const char *at, const char *end)
{
    while (at < end && (*at == ' ' || *at == '\t' || *at == '\r' || *at == '\n')) ++at;
    return at;
}

static int parse_string(const char **cursor, const char *end, char *out, size_t capacity)
{
    const char *at = skip_space(*cursor, end);
    size_t used = 0u;
    if (at == end || *at++ != '"') return 0;
    while (at < end && *at != '"') {
        if (*at == '\\' || (unsigned char)*at < 0x20u || used + 1u >= capacity) return 0;
        out[used++] = *at++;
    }
    if (at == end || *at++ != '"') return 0;
    out[used] = '\0';
    *cursor = at;
    return 1;
}

static int parse_arguments(const char **cursor, const char *end, e06_command_t *command)
{
    const char *at = skip_space(*cursor, end);
    char key[16];
    uint32_t value = 0u;
    if (at == end || *at++ != '{') return 0;
    at = skip_space(at, end);
    if (at < end && *at == '}') { *cursor = at + 1; return 1; }
    if (!parse_string(&at, end, key, sizeof(key)) || strcmp(key, "count") != 0) return 0;
    at = skip_space(at, end);
    if (at == end || *at++ != ':') return 0;
    at = skip_space(at, end);
    if (at == end || *at < '0' || *at > '9') return 0;
    while (at < end && *at >= '0' && *at <= '9') {
        if (value > 100000u) return 0;
        value = value * 10u + (uint32_t)(*at++ - '0');
    }
    at = skip_space(at, end);
    if (at == end || *at++ != '}') return 0;
    command->count = value;
    command->has_count = 1;
    *cursor = at;
    return 1;
}

static int parse_command(const char *json, size_t bytes, e06_command_t *command)
{
    const char *at = skip_space(json, json + bytes);
    const char *end = json + bytes;
    int have_name = 0, have_arguments = 0;
    memset(command, 0, sizeof(*command));
    if (at == end || *at++ != '{') return 0;
    for (;;) {
        char key[16];
        at = skip_space(at, end);
        if (at < end && *at == '}') { ++at; break; }
        if (!parse_string(&at, end, key, sizeof(key))) return 0;
        at = skip_space(at, end);
        if (at == end || *at++ != ':') return 0;
        if (strcmp(key, "name") == 0 && !have_name) {
            if (!parse_string(&at, end, command->name, sizeof(command->name))) return 0;
            have_name = 1;
        } else if (strcmp(key, "arguments") == 0 && !have_arguments) {
            if (!parse_arguments(&at, end, command)) return 0;
            have_arguments = 1;
        } else return 0;
        at = skip_space(at, end);
        if (at < end && *at == ',') { ++at; continue; }
        if (at < end && *at == '}') { ++at; break; }
        return 0;
    }
    return have_name && have_arguments && skip_space(at, end) == end;
}

static int format_telemetry(char *json, size_t capacity, const e06_telemetry_t *telemetry)
{
    char power[32], temperature[24];
    int power_valid = telemetry->power_valid && telemetry->monitored_power_uW >= 0;
    int temperature_valid = telemetry->temperature_valid && telemetry->temperature_mC >= 0;
    if (power_valid) (void)snprintf(power, sizeof(power), "%lld", (long long)telemetry->monitored_power_uW);
    else strcpy(power, "null");
    if (temperature_valid) (void)snprintf(temperature, sizeof(temperature), "%ld", (long)telemetry->temperature_mC);
    else strcpy(temperature, "null");
    return snprintf(json, capacity,
        "{\"completed_frames\":%lu,\"power_uW\":%s,\"sensor_valid\":%s,"
        "\"temperature_mC\":%s,\"timestamp_ticks\":%llu}",
        (unsigned long)completed_frames, power,
        (power_valid && temperature_valid) ? "true" : "false", temperature,
        (unsigned long long)telemetry->timestamp_ticks);
}

static err_t send_telemetry(e06_connection_t *state, uint32_t request_id)
{
    e06_telemetry_t telemetry;
    char json[512];
    int written;
    (void)e06_telemetry_sample(&telemetry);
    written = format_telemetry(json, sizeof(json), &telemetry);
    if (written < 0 || (size_t)written >= sizeof(json))
        return abort_connection(state, "telemetry response overflow");
    return send_json(state, 6u, request_id, json);
}

static err_t send_result(e06_connection_t *state, uint32_t request_id,
                         uint8_t kind, const e06_result_t *result)
{
    char json[512];
    int written = snprintf(json, sizeof(json),
        "{\"mismatch_count\":%lu,\"mm2s_ticks\":%llu,\"pl_ticks\":%llu,"
        "\"predicted_class\":%ld,\"s2mm_ticks\":%llu,\"total_ticks\":%llu}",
        (unsigned long)result->mismatch_count, (unsigned long long)result->mm2s_ticks,
        (unsigned long long)result->pl_ticks, (long)result->predicted_class,
        (unsigned long long)result->s2mm_ticks, (unsigned long long)result->total_ticks);
    if (written < 0 || (size_t)written >= sizeof(json))
        return abort_connection(state, "result response overflow");
    return send_json(state, kind, request_id, json);
}

static err_t run_inference(e06_connection_t *state, uint32_t request_id,
                           uint8_t kind, int include_telemetry)
{
    e06_result_t result;
    err_t status;
    if (e06_inference_run(&result) != E06_OK)
        return send_error(state, request_id, "inference_failed", e06_inference_last_error());
    ++completed_frames;
    status = send_result(state, request_id, kind, &result);
    if (status != ERR_OK || !include_telemetry) return status;
    return send_telemetry(state, request_id);
}

static err_t pump_bulk(e06_connection_t *state)
{
    err_t status;
    /* tcp_write only transfers ownership to lwIP. Service the connection until
     * the entire response (including its prefix) is ACKed, not merely queued.
     * Signed sequence subtraction is wrap-safe for responses < 2^31 bytes. */
    if (state->pcb->lastack != state->bulk_last_ack) {
        state->bulk_last_ack = state->pcb->lastack;
        state->bulk_last_progress = network_ticks();
    }
    if (state->bulk_offset == state->bulk_bytes &&
            (int32_t)(state->pcb->lastack - state->bulk_end_seq) >= 0) {
        state->bulk_active = 0;
        state->bulk_data = NULL;
        return ERR_OK;
    }
    while (state->bulk_active && state->bulk_offset < state->bulk_bytes) {
        size_t remaining = state->bulk_bytes - state->bulk_offset;
        u16_t available = tcp_sndbuf(state->pcb);
        u16_t chunk;
        if (available == 0u) break;
        chunk = available < E07_TX_CHUNK_MAX ? available : E07_TX_CHUNK_MAX;
        if ((size_t)chunk > remaining) chunk = (u16_t)remaining;
        /* sndbuf is credit, not a guarantee that lwIP can allocate the whole
         * write atomically. Back off within this attempt before polling again. */
        for (;;) {
            status = tcp_write(state->pcb, state->bulk_data + state->bulk_offset,
                               chunk, TCP_WRITE_FLAG_COPY);
            if (status != ERR_MEM) break;
            if (state->bulk_mem_retries != UINT32_MAX) ++state->bulk_mem_retries;
            if (chunk == 1u) break;
            chunk = (u16_t)(chunk / 2u);
        }
        if (status == ERR_MEM) break;
        if (status != ERR_OK) return abort_connection(state, "bulk tcp_write failed");
        state->bulk_offset += chunk;
        state->bulk_last_progress = network_ticks();
    }
    status = tcp_output(state->pcb);
    /* Queued data belongs to lwIP now. Temporary NIC/pbuf pressure must not
     * discard the connection or advance the payload offset twice. */
    if (status != ERR_OK && status != ERR_MEM)
        return abort_connection(state, "bulk tcp_output failed");
#ifndef E06_HOST_TEST
    uint64_t now = network_ticks();
    if (state->bulk_active && now - state->bulk_last_progress > 2u * COUNTS_PER_SECOND
            && now - state->bulk_last_diagnostic > 2u * COUNTS_PER_SECOND) {
        state->bulk_last_diagnostic = now;
        E06_NET_LOG("BULK_STALL id=%lu offset=%lu total=%lu sndbuf=%lu queue=%u wnd=%lu cwnd=%lu "
            "ack=%lu next=%lu end=%lu unsent=%u unacked=%u ref=%u nrtx=%u rtime=%d "
            "tcp_ticks=%lu input_busy=%u active_pcb=%u flags=%u out=%d mem_retries=%lu\r\n",
            (unsigned long)state->bulk_request_id,
            (unsigned long)state->bulk_offset, (unsigned long)state->bulk_bytes,
            (unsigned long)tcp_sndbuf(state->pcb), (unsigned int)state->pcb->snd_queuelen,
            (unsigned long)state->pcb->snd_wnd, (unsigned long)state->pcb->cwnd,
            (unsigned long)state->pcb->lastack, (unsigned long)state->pcb->snd_nxt,
            (unsigned long)state->bulk_end_seq,
            state->pcb->unsent ? (unsigned)state->pcb->unsent->len : 0u,
            state->pcb->unacked ? (unsigned)state->pcb->unacked->len : 0u,
            state->pcb->unsent ? (unsigned)state->pcb->unsent->p->ref :
                state->pcb->unacked ? (unsigned)state->pcb->unacked->p->ref : 0u,
            (unsigned)state->pcb->nrtx, (int)state->pcb->rtime,
            (unsigned long)tcp_ticks, (unsigned)(tcp_input_pcb == state->pcb),
            (unsigned)(tcp_active_pcbs == state->pcb), (unsigned)state->pcb->flags,
            (int)status, (unsigned long)state->bulk_mem_retries);
    }
#endif
    return ERR_OK;
}

static err_t start_payload_metadata(e06_connection_t *state, uint32_t request_id, const char *metadata)
{
    size_t metadata_bytes = strlen(metadata);
    const void *data = e06_inference_input_data();
    size_t bytes = e06_inference_input_bytes();
    fvit_header_t header = {1u, request_id, (uint32_t)metadata_bytes, (uint32_t)bytes};
    size_t prefix = FVIT_HEADER_SIZE + metadata_bytes;
    err_t status;
    if (data == NULL || bytes == 0u || bytes > FVIT_MAX_PAYLOAD_BYTES)
        return send_error(state, request_id, "input_unavailable", "fixed E06 input is unavailable");
    if (fvit_header_encode(tx_frame, &header) != FVIT_OK || prefix > sizeof(tx_frame))
        return abort_connection(state, "full payload header failed");
    memcpy(tx_frame + FVIT_HEADER_SIZE, metadata, metadata_bytes);
    status = tcp_write(state->pcb, tx_frame, (u16_t)prefix, TCP_WRITE_FLAG_COPY);
    if (status != ERR_OK) return abort_connection(state, "full payload prefix failed");
    state->bulk_data = (const uint8_t *)data;
    state->bulk_bytes = bytes;
    state->bulk_offset = 0u;
    state->bulk_active = 1;
    state->bulk_last_progress = state->bulk_last_diagnostic = network_ticks();
    state->bulk_mem_retries = 0u;
    state->bulk_end_seq = state->pcb->snd_lbb + (uint32_t)bytes;
    state->bulk_last_ack = state->pcb->lastack;
    state->bulk_request_id = request_id;
    return pump_bulk(state);
}

static err_t start_full_payload(e06_connection_t *state, uint32_t request_id) {
    return start_payload_metadata(state, request_id,
        "{\"fixture\":\"E07_FIXED_INPUT\",\"mode\":\"full_payload\"}");
}

/* Replay is deliberately limited to the exact SD fixture. Unknown image tensors
 * cannot inherit its reference logits or be reported as verified inference. */
static err_t replay(e06_connection_t *state, uint32_t id, int compact) {
    e06_result_t result;
    uint64_t begin = network_ticks(), end, send;
    char json[1024];
    if (state->header.payload_len != e06_inference_input_bytes() || state->payload_mismatch)
        return send_error(state, id, "fixture_mismatch", "replay input differs from verified SD tensor");
    memset(&result, 0, sizeof(result));
    if (compact) {
        if (e06_inference_run(&result) != E06_OK)
            return send_error(state, id, "inference_failed", e06_inference_last_error());
        ++completed_frames;
    }
    end = network_ticks();
    send = network_ticks();
    int n = snprintf(json, sizeof(json),
        "{\"fixture\":\"E07_FIXED_INPUT\",\"mode\":\"replay_%s\","
        "\"edge_rx_start_ticks\":%llu,\"edge_rx_end_ticks\":%llu,"
        "\"inference_start_ticks\":%llu,\"inference_end_ticks\":%llu,"
        "\"result_queue_ticks\":%llu,\"timer_frequency_hz\":%llu,"
        "\"mismatch_count\":%lu,\"predicted_class\":%ld,\"total_ticks\":%llu}",
        compact ? "compact" : "full", (unsigned long long)state->rx_start_ticks,
        (unsigned long long)state->rx_end_ticks, (unsigned long long)begin,
        (unsigned long long)end, (unsigned long long)send,
#ifdef E06_HOST_TEST
        99990005ull,
#else
        (unsigned long long)COUNTS_PER_SECOND,
#endif
        (unsigned long)result.mismatch_count, (long)result.predicted_class,
        (unsigned long long)result.total_ticks);
    if (n < 0 || (size_t)n >= sizeof(json)) return abort_connection(state, "replay metadata overflow");
    return compact ? send_json(state, 2u, id, json) : start_payload_metadata(state, id, json);
}

static err_t repeat_latency(e06_connection_t *state, uint32_t request_id, uint32_t count)
{
    e06_result_t result;
    uint64_t total = 0u, pl = 0u, mm2s = 0u, s2mm = 0u;
    char json[512];
    uint32_t index;
    int written;
    for (index = 0u; index < count; ++index) {
        if (e06_inference_run(&result) != E06_OK)
            return send_error(state, request_id, "inference_failed", e06_inference_last_error());
        ++completed_frames;
        total += result.total_ticks; pl += result.pl_ticks;
        mm2s += result.mm2s_ticks; s2mm += result.s2mm_ticks;
    }
    written = snprintf(json, sizeof(json),
        "{\"count\":%lu,\"mm2s_ticks\":%llu,\"pl_ticks\":%llu,"
        "\"s2mm_ticks\":%llu,\"status\":\"ok\",\"total_ticks\":%llu}",
        (unsigned long)count, (unsigned long long)mm2s, (unsigned long long)pl,
        (unsigned long long)s2mm, (unsigned long long)total);
    if (written < 0 || (size_t)written >= sizeof(json))
        return abort_connection(state, "repeat response overflow");
    return send_json(state, 4u, request_id, json);
}

static err_t handle_frame(e06_connection_t *state)
{
    e06_command_t command;
    uint32_t id = state->header.request_id;
    if (!parse_command(state->metadata, state->metadata_used, &command))
        return send_error(state, id, "malformed_command", "invalid command metadata");
    if (strcmp(command.name, "repeat_latency") == 0) {
        if (!command.has_count || command.count == 0u || command.count > E06_REPEAT_MAX)
            return send_error(state, id, "invalid_count", "count must be in 1..16");
        return repeat_latency(state, id, command.count);
    }
    if (command.has_count)
        return send_error(state, id, "unexpected_arguments", "command takes empty arguments");
    if (strcmp(command.name, "replay_compact") == 0) return replay(state, id, 1);
    if (strcmp(command.name, "replay_full") == 0) return replay(state, id, 0);
    if (state->header.payload_len)
        return send_error(state, id, "unexpected_payload", "payload only allowed for replay commands");
    if (strcmp(command.name, "time_sync") == 0) {
        char json[256];
        (void)snprintf(json, sizeof(json), "{\"edge_rx_ticks\":%llu,\"edge_tx_ticks\":%llu,\"timer_frequency_hz\":%llu}",
            (unsigned long long)state->rx_start_ticks, (unsigned long long)network_ticks(),
#ifdef E06_HOST_TEST
            99990005ull);
#else
            (unsigned long long)COUNTS_PER_SECOND);
#endif
        return send_json(state, 4u, id, json);
    }
    if (strcmp(command.name, "health") == 0)
        return send_json(state, 4u, id,
            "{\"model\":\"E07\",\"phase\":\"E07_PHYSICAL\",\"status\":\"ok\"}");
    if (strcmp(command.name, "telemetry") == 0) return send_telemetry(state, id);
    if (strcmp(command.name, "run_once") == 0) return run_inference(state, id, 8u, 1);
    if (strcmp(command.name, "compact_result") == 0) return run_inference(state, id, 2u, 0);
    if (strcmp(command.name, "full_payload") == 0) return start_full_payload(state, id);
    return send_error(state, id, "unknown_command", command.name);
}

static err_t consume_byte(e06_connection_t *state, uint8_t byte)
{
    if (!state->header_ready) {
        if (!state->header_used) state->rx_start_ticks = network_ticks();
        state->header_bytes[state->header_used++] = byte;
        if (state->header_used == FVIT_HEADER_SIZE) {
            if (fvit_header_decode(&state->header, state->header_bytes) != FVIT_OK) {
                err_t sent = send_error(state, 0u, "invalid_header", "header validation failed");
                if (sent == ERR_ABRT) return ERR_ABRT;
                return abort_connection(state, "invalid header");
            }
            if (state->header.kind != 7u || (state->header.payload_len != 0u &&
                    (state->header.metadata_len == 0u ||
                     state->header.payload_len != e06_inference_input_bytes()))) {
                err_t sent = send_error(state, state->header.request_id,
                                        "unsupported_frame", "expected command without payload");
                if (sent == ERR_ABRT) return ERR_ABRT;
                return abort_connection(state, "unsupported inbound frame");
            }
            state->header_ready = 1;
            if (state->header.metadata_len == 0u) {
                err_t status = handle_frame(state);
                if (status != ERR_ABRT) reset_parser(state);
                return status;
            }
        }
        return ERR_OK;
    }
    if (state->metadata_used == state->header.metadata_len && state->header.payload_len) {
        const uint8_t *input = (const uint8_t *)e06_inference_input_data();
        if (!input || byte != input[state->payload_used]) state->payload_mismatch = 1;
        ++state->payload_used;
        if (state->payload_used == state->header.payload_len) {
            state->rx_end_ticks = network_ticks();
            err_t status = handle_frame(state);
            if (status != ERR_ABRT) reset_parser(state);
            return status;
        }
        return ERR_OK;
    }
    state->metadata[state->metadata_used++] = (char)byte;
    if (state->metadata_used == state->header.metadata_len) {
        err_t status;
        state->metadata[state->metadata_used] = '\0';
        if (state->header.payload_len) return ERR_OK;
        state->rx_end_ticks = network_ticks();
        status = handle_frame(state);
        if (status != ERR_ABRT) reset_parser(state);
        return status;
    }
    return ERR_OK;
}

static err_t receive_callback(void *argument, struct tcp_pcb *pcb,
                              struct pbuf *packet, err_t error)
{
    e06_connection_t *state = (e06_connection_t *)argument;
    struct pbuf *part;
    err_t status = ERR_OK;
    u16_t consumed = 0u;
    if (state == NULL || state->pcb != pcb) return ERR_ARG;
    if (error != ERR_OK) return abort_connection(state, "receive callback error");
    if (packet == NULL) return close_connection(state, "remote close");
    if (state->bulk_active) {
        pbuf_free(packet);
        return abort_connection(state, "command received during bulk response");
    }
    for (part = packet; part != NULL && status == ERR_OK; part = part->next) {
        const uint8_t *bytes = (const uint8_t *)part->payload;
        size_t index;
        for (index = 0u; index < part->len;) {
#if E07_BATCH_VERIFY
            if (state->header_ready && state->header.payload_len
                    && state->metadata_used == state->header.metadata_len) {
                size_t count = part->len - index;
                size_t remaining = state->header.payload_len - state->payload_used;
                const uint8_t *input = (const uint8_t *)e06_inference_input_data();
                if (count > remaining) count = remaining;
                if (!input || memcmp(bytes + index, input + state->payload_used, count) != 0)
                    state->payload_mismatch = 1;
                state->payload_used += count;
                index += count;
                consumed = (u16_t)(consumed + count);
                if (state->payload_used == state->header.payload_len) {
                    state->rx_end_ticks = network_ticks();
                    status = handle_frame(state);
                    if (status != ERR_ABRT) reset_parser(state);
                }
                if (status != ERR_OK) break;
                continue;
            }
#endif
            status = consume_byte(state, bytes[index]);
            ++index;
            ++consumed;
            if (status != ERR_OK) break;
        }
    }
    if (status != ERR_ABRT && consumed != 0u) tcp_recved(pcb, consumed);
    pbuf_free(packet);
    return status;
}

static err_t sent_callback(void *argument, struct tcp_pcb *pcb, u16_t bytes)
{
    e06_connection_t *state = (e06_connection_t *)argument;
    (void)bytes;
    if (state == NULL || state->pcb != pcb) return ERR_ARG;
    return state->bulk_active ? pump_bulk(state) : ERR_OK;
}

static void error_callback(void *argument, err_t error)
{
    e06_connection_t *state = (e06_connection_t *)argument;
    E06_NET_LOG("NETWORK_TCP_ERROR=%d\r\n", (int)error);
    (void)error;
    if (state != NULL) release_state(state);
}

static err_t connected_callback(void *argument, struct tcp_pcb *pcb, err_t error)
{
    static const char hello[] =
        "{\"artifact_hashes\":{\"bitstream\":\"" E06_BITSTREAM_SHA256 "\","
        "\"input\":\"" E06_INPUT_SHA256 "\",\"output\":\"" E06_OUTPUT_SHA256 "\","
        "\"weights\":\"" E06_WEIGHTS_SHA256 "\",\"xsa\":\"" E06_XSA_SHA256 "\"},"
        "\"board_ip\":\"" E06_BOARD_IP_TEXT "\",\"firmware_sha256\":\"" E06_FIRMWARE_SHA256 "\","
        "\"model\":\"E07\",\"phase\":\"E07_PHYSICAL\",\"tcp_port\":5001}";
    e06_connection_t *state = (e06_connection_t *)argument;
    if (state == NULL || state->pcb != pcb) return ERR_ARG;
    if (error != ERR_OK) return abort_connection(state, "connect callback failed");
    state->connected = 1;
    tcp_recv(pcb, receive_callback);
    tcp_sent(pcb, sent_callback);
    E06_NET_LOG("NETWORK_CONNECTED=192.168.10.1:%u\r\n", (unsigned int)E06_TCP_PORT);
    return send_json(state, 5u, 0u, hello);
}

static int begin_connect(void)
{
    struct tcp_pcb *pcb;
    err_t status;
    if (connection.pcb != NULL) return 0;
    pcb = tcp_new_ip_type(IPADDR_TYPE_ANY);
    if (pcb == NULL) { E06_NET_LOG("NETWORK_PCB_ALLOC_FAIL\r\n"); return -1; }
    connection.pcb = pcb;
    connection.connected = 0;
    reset_parser(&connection);
    tcp_arg(pcb, &connection);
    tcp_err(pcb, error_callback);
#ifndef E06_HOST_TEST
    tcp_nagle_disable(pcb);
#endif
    status = tcp_connect(pcb, &collector_address, E06_TCP_PORT, connected_callback);
    if (status == ERR_OK) return 0;
    E06_NET_LOG("NETWORK_CONNECT_START_FAIL=%d\r\n", (int)status);
    detach_callbacks(pcb);
    release_state(&connection);
    tcp_abort(pcb);
    return -1;
}

int e06_network_start(void)
{
    ip_addr_t address, mask, gateway;
    static unsigned char mac[6] = {0x02u, 0x00u, 0x00u, 0x00u, 0x10u, 0x02u};
    memset(&connection, 0, sizeof(connection));
    completed_frames = 0u;
    reconnect_polls = 0u;
#ifndef E06_HOST_TEST
    memset(&gem_tx_service, 0, sizeof(gem_tx_service));
#endif
    lwip_init();
    IP4_ADDR(&address, E06_BOARD_IP_A, E06_BOARD_IP_B, E06_BOARD_IP_C, E06_BOARD_IP_D);
    IP4_ADDR(&mask, E06_NETMASK_A, E06_NETMASK_B, E06_NETMASK_C, E06_NETMASK_D);
    IP4_ADDR(&gateway, E06_GATEWAY_IP_A, E06_GATEWAY_IP_B, E06_GATEWAY_IP_C, E06_GATEWAY_IP_D);
    IP4_ADDR(&collector_address, E06_GATEWAY_IP_A, E06_GATEWAY_IP_B,
             E06_GATEWAY_IP_C, E06_GATEWAY_IP_D);
    if (xemac_add(&e06_netif, &address, &mask, &gateway, mac,
                  XPAR_XEMACPS_0_BASEADDR) == NULL) {
        E06_NET_LOG("NETWORK_NETIF_INIT_FAIL\r\n"); return -1;
    }
    netif_set_default(&e06_netif);
    netif_set_up(&e06_netif);
#ifndef E06_HOST_TEST
    platform_start_network_timer();
#endif
    if (begin_connect() != 0) E06_NET_LOG("NETWORK_RECONNECT_SCHEDULED\r\n");
    return 0;
}

void e06_network_poll(void)
{
    (void)xemacif_input(&e06_netif);
#ifdef E06_HOST_TEST
    sys_check_timeouts();
#else
    e07_gem_tx_poll(&gem_tx_service, &e06_netif, get_time_ms());
    platform_poll_network_timer();
#endif
    if (connection.pcb != NULL) {
        if (connection.connected && connection.bulk_active)
            (void)pump_bulk(&connection);
        return;
    }
    if (reconnect_polls != 0u) { --reconnect_polls; return; }
    if (begin_connect() != 0) reconnect_polls = E06_RECONNECT_POLLS;
}
