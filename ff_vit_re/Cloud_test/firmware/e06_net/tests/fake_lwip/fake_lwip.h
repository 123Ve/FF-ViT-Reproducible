#ifndef E06_FAKE_LWIP_H
#define E06_FAKE_LWIP_H
#ifndef E06_HOST_TEST
#error "fake_lwip.h is host-test only"
#endif
#include <stddef.h>
#include <stdint.h>
typedef int err_t;
typedef uint16_t u16_t;
typedef uint8_t u8_t;
#define ERR_OK 0
#define ERR_MEM (-1)
#define ERR_ARG (-2)
#define ERR_USE (-3)
#define ERR_ABRT (-4)
#define TCP_WRITE_FLAG_COPY 1u
#define IPADDR_TYPE_ANY 0u
#define XPAR_XEMACPS_0_BASEADDR 0x1000u
typedef struct ip4_addr { uint32_t addr; } ip4_addr_t;
typedef ip4_addr_t ip_addr_t;
#define IP4_ADDR(ip, a, b, c, d) ((ip)->addr = ((uint32_t)(a) | ((uint32_t)(b) << 8) | ((uint32_t)(c) << 16) | ((uint32_t)(d) << 24)))
typedef struct netif { int is_up; } netif;
typedef struct pbuf { struct pbuf *next; void *payload; u16_t len; u16_t tot_len; } pbuf;
struct tcp_pcb;
typedef err_t (*tcp_connected_fn)(void *, struct tcp_pcb *, err_t);
typedef err_t (*tcp_recv_fn)(void *, struct tcp_pcb *, struct pbuf *, err_t);
typedef err_t (*tcp_sent_fn)(void *, struct tcp_pcb *, u16_t);
typedef void (*tcp_err_fn)(void *, err_t);
typedef struct tcp_pcb {
    void *callback_arg;
    tcp_connected_fn connected_cb;
    tcp_recv_fn recv_cb;
    tcp_sent_fn sent_cb;
    tcp_err_fn err_cb;
    uint16_t remote_port;
    uint16_t sndbuf;
    uint32_t snd_lbb, lastack;
    int valid, closed, aborted;
} tcp_pcb;
void lwip_init(void);
struct netif *xemac_add(struct netif *, const ip_addr_t *, const ip_addr_t *, const ip_addr_t *, const unsigned char *, unsigned long);
void netif_set_default(struct netif *);
void netif_set_up(struct netif *);
int xemacif_input(struct netif *);
void sys_check_timeouts(void);
struct tcp_pcb *tcp_new_ip_type(uint8_t);
err_t tcp_connect(struct tcp_pcb *, const ip_addr_t *, uint16_t, tcp_connected_fn);
void tcp_arg(struct tcp_pcb *, void *);
void tcp_recv(struct tcp_pcb *, tcp_recv_fn);
void tcp_sent(struct tcp_pcb *, tcp_sent_fn);
void tcp_err(struct tcp_pcb *, tcp_err_fn);
void tcp_recved(struct tcp_pcb *, u16_t);
u16_t tcp_sndbuf(const struct tcp_pcb *);
err_t tcp_write(struct tcp_pcb *, const void *, u16_t, u8_t);
err_t tcp_output(struct tcp_pcb *);
err_t tcp_close(struct tcp_pcb *);
void tcp_abort(struct tcp_pcb *);
void pbuf_free(struct pbuf *);
unsigned fake_output_calls(void);
#endif
