#include "fake_lwip.h"
#include <string.h>
#define FAKE_MAX_PCBS 32
#define FAKE_WIRE_BYTES (1024u * 1024u)
#define FAKE_SNDBUF 65535u
#define FAKE_INPUT_BYTES 602112u
static struct tcp_pcb pcbs[FAKE_MAX_PCBS];
static size_t pcb_count;
static struct netif *default_netif;
static unsigned char wire[FAKE_WIRE_BYTES];
static size_t wire_size;
static unsigned long recved_bytes;
static int write_failure, output_failure, close_failure;
static u16_t write_limit = FAKE_SNDBUF;
static int post_invalidation_calls;
static int inference_calls, telemetry_calls;
static uint32_t configured_ip, configured_mask, configured_gateway, connected_ip;
static unsigned char input_bytes[FAKE_INPUT_BYTES];
static int input_ready;
static unsigned output_calls;
unsigned fake_output_calls(void) { return output_calls; }
static int usable(const struct tcp_pcb *pcb) { if (pcb && pcb->valid) return 1; ++post_invalidation_calls; return 0; }
void fake_lwip_reset(void) {
    memset(pcbs, 0, sizeof(pcbs)); pcb_count = 0u; default_netif = NULL;
    wire_size = 0u; recved_bytes = 0u; write_failure = output_failure = close_failure = 0;
    write_limit = FAKE_SNDBUF;
    output_calls = 0;
    post_invalidation_calls = inference_calls = telemetry_calls = 0;
    configured_ip = configured_mask = configured_gateway = connected_ip = 0u;
}
struct tcp_pcb *fake_last_pcb(void) { return pcb_count ? &pcbs[pcb_count - 1u] : NULL; }
size_t fake_pcb_count(void) { return pcb_count; }
const unsigned char *fake_wire(void) { return wire; }
size_t fake_wire_size(void) { return wire_size; }
void fake_wire_clear(void) { wire_size = 0u; }
unsigned long fake_recved_bytes(void) { return recved_bytes; }
void fake_fail_write(int v) { write_failure = v; }
void fake_write_limit(u16_t v) { write_limit = v; }
void fake_fail_output(int v) { output_failure = v; }
void fake_fail_close(int v) { close_failure = v; }
int fake_post_invalidation_calls(void) { return post_invalidation_calls; }
int fake_inference_calls(void) { return inference_calls; }
int fake_telemetry_calls(void) { return telemetry_calls; }
uint32_t fake_configured_ip(void) { return configured_ip; }
uint32_t fake_configured_mask(void) { return configured_mask; }
uint32_t fake_configured_gateway(void) { return configured_gateway; }
uint32_t fake_connected_ip(void) { return connected_ip; }
err_t fake_connect_success(void) {
    struct tcp_pcb *pcb = fake_last_pcb();
    if (!usable(pcb) || !pcb->connected_cb) return ERR_ARG;
    return pcb->connected_cb(pcb->callback_arg, pcb, ERR_OK);
}
void fake_remote_error(err_t error) {
    struct tcp_pcb *pcb = fake_last_pcb(); void *arg; tcp_err_fn cb;
    if (!usable(pcb) || !pcb->err_cb) return;
    arg = pcb->callback_arg; cb = pcb->err_cb; pcb->valid = 0; cb(arg, error);
}
void fake_ack_all(void) {
    struct tcp_pcb *pcb = fake_last_pcb();
    if (!usable(pcb)) return;
    pcb->sndbuf = FAKE_SNDBUF;
    pcb->lastack = pcb->snd_lbb;
    if (pcb->sent_cb) (void)pcb->sent_cb(pcb->callback_arg, pcb, FAKE_SNDBUF);
}
void lwip_init(void) {}
struct netif *xemac_add(struct netif *n, const ip_addr_t *ip, const ip_addr_t *mask,
                       const ip_addr_t *gateway, const unsigned char *mac, unsigned long base) {
    configured_ip = ip->addr; configured_mask = mask->addr; configured_gateway = gateway->addr;
    (void)mac; (void)base; return n;
}
void netif_set_default(struct netif *n) { default_netif = n; }
void netif_set_up(struct netif *n) { n->is_up = 1; }
int xemacif_input(struct netif *n) { return n == default_netif; }
void sys_check_timeouts(void) {}
struct tcp_pcb *tcp_new_ip_type(uint8_t type) {
    struct tcp_pcb *pcb; (void)type;
    if (pcb_count == FAKE_MAX_PCBS) return NULL;
    pcb = &pcbs[pcb_count++]; memset(pcb, 0, sizeof(*pcb)); pcb->valid = 1; pcb->sndbuf = FAKE_SNDBUF; return pcb;
}
err_t tcp_connect(struct tcp_pcb *pcb, const ip_addr_t *ip, uint16_t port, tcp_connected_fn cb) {
    if (!usable(pcb)) return ERR_ARG;
    connected_ip = ip->addr; pcb->remote_port = port; pcb->connected_cb = cb;
    return ERR_OK;
}
void tcp_arg(struct tcp_pcb *pcb, void *arg) { if (usable(pcb)) pcb->callback_arg = arg; }
void tcp_recv(struct tcp_pcb *pcb, tcp_recv_fn cb) { if (usable(pcb)) pcb->recv_cb = cb; }
void tcp_sent(struct tcp_pcb *pcb, tcp_sent_fn cb) { if (usable(pcb)) pcb->sent_cb = cb; }
void tcp_err(struct tcp_pcb *pcb, tcp_err_fn cb) { if (usable(pcb)) pcb->err_cb = cb; }
void tcp_recved(struct tcp_pcb *pcb, u16_t amount) { if (usable(pcb)) recved_bytes += amount; }
u16_t tcp_sndbuf(const struct tcp_pcb *pcb) { return usable(pcb) ? pcb->sndbuf : 0u; }
err_t tcp_write(struct tcp_pcb *pcb, const void *data, u16_t size, u8_t flags) {
    if (!usable(pcb)) return ERR_ARG;
    if (write_failure || size > write_limit || flags != TCP_WRITE_FLAG_COPY || size > pcb->sndbuf || wire_size + size > sizeof(wire)) return ERR_MEM;
    memcpy(wire + wire_size, data, size); wire_size += size;
    pcb->snd_lbb += size;
    pcb->sndbuf = (u16_t)(pcb->sndbuf - size); return ERR_OK;
}
err_t tcp_output(struct tcp_pcb *pcb) {
    ++output_calls;
    return usable(pcb) ? (output_failure ? ERR_MEM : ERR_OK) : ERR_ARG;
}
err_t tcp_close(struct tcp_pcb *pcb) {
    if (!usable(pcb)) return ERR_ARG;
    if (close_failure) return ERR_MEM;
    pcb->closed = 1; pcb->valid = 0; return ERR_OK;
}
void tcp_abort(struct tcp_pcb *pcb) { if (usable(pcb)) { pcb->aborted = 1; pcb->valid = 0; } }
void pbuf_free(struct pbuf *p) { (void)p; }

#include "e06_inference.h"
#include "e06_telemetry.h"
int e06_inference_init(const char *w, const char *i, const char *r) { (void)w; (void)i; (void)r; return E06_OK; }
int e06_inference_run(e06_result_t *out) {
    ++inference_calls; out->mismatch_count = 0; out->predicted_class = 17;
    out->total_ticks = 101; out->pl_ticks = 80; out->mm2s_ticks = 10; out->s2mm_ticks = 11; return E06_OK;
}
const void *e06_inference_input_data(void) {
    size_t i; if (!input_ready) { for (i = 0; i < sizeof(input_bytes); ++i) input_bytes[i] = (unsigned char)(i & 0xffu); input_ready = 1; }
    return input_bytes;
}
size_t e06_inference_input_bytes(void) { return sizeof(input_bytes); }
const char *e06_inference_last_error(void) { return "fake inference error"; }
int e06_telemetry_init(void) { return E06_OK; }
int e06_telemetry_sample(e06_telemetry_t *out) {
    ++telemetry_calls; out->timestamp_ticks = 202; out->monitored_power_uW = 3000000;
    out->temperature_mC = 42000; out->power_valid = 1; out->temperature_valid = 1; return E06_OK;
}
const char *e06_telemetry_last_error(void) { return "fake telemetry error"; }
