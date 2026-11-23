#ifndef INDEPENDENT_MONITOR_H
#define INDEPENDENT_MONITOR_H
#include <stdint.h>
#include <stddef.h>
#define M_MAGIC 0x314d5049u
#define M_VERSION 4u
#define M_RAILS 18u
#define M_ALL_RAILS 0x3ffffu
#ifndef E07_PROFILE_RAILS
#define E07_PROFILE_RAILS 18
#endif
#ifndef M_BUILD_ID
#define M_BUILD_ID "native-test"
#endif
#if E07_PROFILE_RAILS == 16
#define M_REQUIRED_RAILS 0x37f7fu
#define M_PROFILE_JSON "\"measurement_profile\":\"diagnostic16\",\"scope\":\"16-rail diagnostic\",\"included_mask\":229247,\"included_count\":16,\"excluded_rails\":[7,15],"
#elif E07_PROFILE_RAILS == 17
#define M_REQUIRED_RAILS 0x3ff7fu
#define M_PROFILE_JSON "\"measurement_profile\":\"diagnostic17\",\"scope\":\"17-rail diagnostic\",\"included_mask\":262015,\"included_count\":17,\"excluded_rails\":[7],"
#elif E07_PROFILE_RAILS == 18
#define M_REQUIRED_RAILS M_ALL_RAILS
#define M_PROFILE_JSON "\"measurement_profile\":\"strict18\",\"scope\":\"18 monitored supply rails; not external whole-board input power\",\"included_mask\":262143,\"included_count\":18,\"excluded_rails\":[],"
#else
#error Unsupported measurement profile
#endif
#define M_CONFIG ((1u<<14)|(2u<<9)|(4u<<6)|(4u<<3)|7u)
#define M_CAL 2048u
#define M_RAIL_CAP 180000u
#define M_EVENT_CAP 262144u
#define M_TEMP_CAP 1024u
#define M_SHARED_BASE 0x30000000ull
#define M_SHARED_BYTES 0x04000000ull
#define M_VALID 1u
#define M_FRESH 2u
#define M_I2C_ERROR 4u
#define M_OVERFLOW 8u
#define M_SATURATED 16u
#define M_STALE 32u
#define M_CONFIG_ERROR 64u
#define M_CLOCK_ERROR 128u
#define M_NEGATIVE 256u
#define M_NOT_READY 512u
#define M_FAULT_CONFIG 1u
#define M_FAULT_SENSOR 2u
#define M_FAULT_BUFFER 4u
#define M_FAULT_HANDSHAKE 8u
#define M_FAULT_INFERENCE 16u
#define M_FAULT_INPUT 32u
#define M_FAULT_NETWORK 64u
#define M_FAULT_TEMP 128u
enum { M_IDLE=0, M_GUARD=1, M_ACTIVE=2, M_POST=3, M_DONE=4 };
enum { M_LOAD_IDLE=0, M_LOAD_FULL=1, M_LOAD_COMPACT=2, M_LOAD_CONTINUOUS=3 };
enum { M_CMD_NONE=0, M_CMD_ARM=1, M_CMD_RELEASE=2 };
enum { M_EVENT_ARM=1, M_EVENT_START=2, M_EVENT_END=3, M_EVENT_FINISH=4,
       M_EVENT_ACK=5, M_EVENT_INFERENCE=6, M_EVENT_INPUT_ERROR=7,
       M_EVENT_INFERENCE_ERROR=8, M_EVENT_FAULT=9, M_EVENT_CLOCK=10, M_EVENT_LOAD=11 };
typedef struct { const char *name; uint8_t domain,address; uint32_t shunt_uohm; } m_rail;
extern const m_rail m_rails[M_RAILS];
typedef struct {
    void *ctx;
    int (*select)(void *, uint8_t);
    int (*read)(void *, uint8_t, uint8_t, uint16_t *);
    int (*write)(void *, uint8_t, uint8_t, uint16_t);
    uint64_t (*ticks)(void *);
} m_io;
typedef struct {
    uint32_t rail, flags;
    uint16_t manufacturer, die, config, calibration;
    uint64_t begin, end;
} m_config_record;
typedef struct {
    uint32_t seq, phase, scan, flags;
    uint16_t rail, config, calibration, shunt, bus, current, power, mask;
    uint64_t begin[5], end[5];
    int64_t power_uW;
    uint64_t scan_start;
} m_rail_record;
typedef struct {
    uint32_t seq, phase, type, request_id, mode, flags, mismatch_count, reserved;
    uint64_t begin, end, tick, aux;
} m_event;
typedef struct {
    uint32_t seq, phase, flags, raw;
    uint64_t tick;
    int32_t temperature_mC;
    uint32_t reserved;
} m_temperature;
typedef struct {
    uint32_t magic, version, core, enabled, mode, scan_ms, offset_ms, command;
    uint32_t phase, command_seq, ping_seq, profile_rails;
    char build_identity[65];
    uint64_t epoch, hz, heartbeat, ping_tick, t0, t1;
} m_control;
typedef struct {
    uint32_t core, configured, faults, phase, state, rail_count, temp_count, scan_count;
    uint32_t i2c_errors, invalid_samples, stale_samples, scan_overruns, overflows;
    uint32_t temp_errors, ping_seq, enabled;
    uint32_t conversion_ready, initializing_samples, observed_mask, excluded_negative_samples, profile_rails;
    uint32_t included_negative_samples;
    uint64_t epoch, hz, heartbeat, ping_tick, configured_tick, scan_start;
    int32_t temperature_mC;
    uint32_t temperature_valid;
    uint64_t temperature_tick;
} m_status;
typedef struct {
    m_control control __attribute__((aligned(64)));
    uint32_t status_seq __attribute__((aligned(64)));
    m_status status;
    uint32_t latest_seq __attribute__((aligned(64)));
    m_rail_record latest[M_RAILS];
    m_config_record configuration[M_RAILS] __attribute__((aligned(64)));
    m_rail_record rails[M_RAIL_CAP] __attribute__((aligned(64)));
    m_temperature temperatures[M_TEMP_CAP] __attribute__((aligned(64)));
    m_event events[M_EVENT_CAP] __attribute__((aligned(64)));
} m_shared;
typedef struct {
    m_shared *shared;
    uint64_t hz, epoch, t0, t1, last_heartbeat, last_ping, ping_sent;
    uint32_t phase, state, faults, event_count, completed_full, completed_compact;
    uint32_t completed_continuous, clock_checks, heartbeat_advances, last_pong;
    uint32_t start_logged, end_logged, pending_ack, pending_id, pending_mode, pending_end_seq;
    uint64_t pending_begin, pending_end, continuous_begin, continuous_end;
    /* Core0's platform clock is sampled after a coherent status read. */
    uint64_t (*clock_ticks)(void);
    uint64_t last_clock_sent,last_clock_sampler,last_clock_received;
    uint32_t last_clock_flags,clock_rejections;
} m_service;
int m_configure(m_io *, unsigned, m_config_record *);
int m_sample(m_io *, unsigned, uint64_t, uint64_t *, m_rail_record *);
int64_t m_power_uW(unsigned, uint16_t);
int m_publish_rail(m_shared *, m_status *, const m_rail_record *);
int m_publish_temp(m_shared *, m_status *, const m_temperature *);
void m_status_publish(m_shared *, const m_status *);
int m_status_read(const m_shared *, m_status *);
void m_latest_publish(m_shared *,const m_rail_record [M_RAILS]);
int m_latest_read(const m_shared *,m_rail_record [M_RAILS]);
void m_service_init(m_service *, m_shared *, uint64_t, unsigned, uint64_t);
void m_service_poll(m_service *, uint64_t);
int m_service_ready(const m_service *, uint64_t);
int m_arm(m_service *, uint32_t, uint64_t);
int m_finish(m_service *, uint64_t);
int m_release(m_service *);
int m_event_add(m_service *, m_event);
void m_fail(m_service *, uint32_t, uint32_t, uint64_t);
int m_ack_begin(m_service *, uint32_t, uint32_t, uint32_t, uint64_t, uint64_t);
void m_ack_poll(m_service *, uint32_t, uint64_t);
void m_inference_event(m_service *, uint32_t, uint64_t, uint64_t, uint32_t, int);
uint64_t m_ticks(void);
uint64_t m_frequency(void);
unsigned m_core_id(void);
void m_map_shared(void);
extern m_service m_runtime;
#ifdef E06_HOST_TEST
extern uint64_t m_test_ticks;
#endif
_Static_assert(sizeof(m_rail_record)==128, "rail wire size");
_Static_assert(sizeof(m_config_record)==32, "config wire size");
_Static_assert(sizeof(m_event)==64, "event wire size");
_Static_assert(sizeof(m_temperature)==32, "temperature wire size");
_Static_assert(sizeof(m_shared)<M_SHARED_BYTES, "shared DDR reservation");
_Static_assert(M_RAIL_CAP >= ((153000u+16u)/17u)*M_RAILS, "150s plus guards and handshake margin at 17ms");
#endif
