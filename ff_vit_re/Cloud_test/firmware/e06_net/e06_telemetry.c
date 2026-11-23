#include "e06_telemetry.h"
#include <math.h>
#include <stddef.h>
#include <string.h>
#ifdef E06_HOST_TEST
#include "tests/fake_bsp/e06_fake_bsp.h"
#else
#include "xiicps.h"
#include "xparameters.h"
#include "xstatus.h"
#include "xsysmonpsu.h"
#include "xiltimer.h"
#endif

#define E06_I2C_MUX_ADDRESS 0x75u
#define E06_I2C_CLOCK_HZ 400000u
#define E06_MUX_ENABLE 0x04u
#define E06_I2C_RETRIES 3
#define INA226_MANUFACTURER_ID 0x5449u
#define INA226_DIE_ID 0x2260u
typedef struct { uint8_t domain, address; uint32_t shunt_uohm; } PowerRail;
/* Vendor ZCU102 rail order: ten PS rails, then eight PL rails. */
static const PowerRail rails[] = {
    {0,0x40,5000}, /* VCCPSINTFP */
    {0,0x41,5000}, /* VCCPSINTLP */
    {0,0x42,5000}, /* VCCPSAUX */
    {0,0x43,5000}, /* VCCPSPLL */
    {0,0x44,5000}, /* MGTRAVCC */
    {0,0x45,5000}, /* MGTRAVTT */
    {0,0x46,5000}, /* VCCO_PSDDR_504 */
    {0,0x47,5000}, /* VCCOPS */
    {0,0x4a,5000}, /* VCCOPS3 */
    {0,0x4b,5000}, /* VCCPSDDRPLL */
    {1,0x40,2000}, /* VCCINT */
    {1,0x41,5000}, /* VCCBRAM */
    {1,0x42,5000}, /* VCCAUX */
    {1,0x43,5000}, /* VCC1V2 */
    {1,0x44,5000}, /* VCC3V3 */
    {1,0x45,5000}, /* VADJ_FMC */
    {1,0x46,5000}, /* MGTAVCC */
    {1,0x47,5000}  /* MGTAVTT */
};
static XIicPs power_iic;
static XSysMonPsu sysmon;
static int initialized, power_ready, temperature_ready;
static const char *last_error = "";
static int fail(int status, const char *message) { last_error = message; return status; }
const char *e06_telemetry_last_error(void) { return last_error; }

static int wait_idle(void) {
    unsigned int remaining = 1000000u;
    while (XIicPs_BusIsBusy(&power_iic) && remaining != 0u) --remaining;
    return remaining ? E06_OK : E06_ERR_SENSOR;
}
static int select_domain(uint8_t domain) {
    uint8_t command = E06_MUX_ENABLE | domain;
    if (XIicPs_MasterSendPolled(&power_iic, &command, 1, E06_I2C_MUX_ADDRESS)
        != XST_SUCCESS) return E06_ERR_SENSOR;
    return wait_idle();
}
static int read_register(uint8_t address, uint8_t reg, uint16_t *value) {
    uint8_t bytes[2];
    if (XIicPs_MasterSendPolled(&power_iic, &reg, 1, address) != XST_SUCCESS ||
        wait_idle() != E06_OK ||
        XIicPs_MasterRecvPolled(&power_iic, bytes, 2, address) != XST_SUCCESS ||
        wait_idle() != E06_OK) return E06_ERR_SENSOR;
    *value = (uint16_t)(((uint16_t)bytes[0] << 8) | bytes[1]);
    return E06_OK;
}
static int identify(const PowerRail *rail) {
    uint16_t manufacturer, die;
    if (select_domain(rail->domain) != E06_OK ||
        read_register(rail->address, 0xfeu, &manufacturer) != E06_OK ||
        read_register(rail->address, 0xffu, &die) != E06_OK)
        return E06_ERR_SENSOR;
    return manufacturer == INA226_MANUFACTURER_ID && (die & 0xfff0u) == INA226_DIE_ID
               ? E06_OK : E06_ERR_SENSOR;
}
static int read_power(const PowerRail *rail, int64_t *power_uW) {
    uint16_t shunt, bus;
    for (int attempt = 0; attempt < E06_I2C_RETRIES; ++attempt) {
        if (identify(rail) == E06_OK &&
            read_register(rail->address, 0x01u, &shunt) == E06_OK &&
            read_register(rail->address, 0x02u, &bus) == E06_OK) {
            /* Same integer scaling/order as vendor power_math.c. */
            int64_t bus_uV = (int64_t)bus * 1250;
            int64_t current_uA = ((int64_t)(int16_t)shunt * 2500 * 1000) /
                                 rail->shunt_uohm;
            *power_uW = (bus_uV * current_uA) / 1000000;
            return E06_OK;
        }
    }
    return E06_ERR_SENSOR;
}

int e06_telemetry_init(void) {
    int probes_ok = 1;
    XIicPs_Config *ic = XIicPs_LookupConfig(XPAR_XIICPS_0_BASEADDR);
    XSysMonPsu_Config *sc = XSysMonPsu_LookupConfig(XPAR_XSYSMONPSU_0_BASEADDR);
    initialized = 1;
    power_ready = ic &&
        XIicPs_CfgInitialize(&power_iic, ic, ic->BaseAddress) == XST_SUCCESS &&
        XIicPs_SelfTest(&power_iic) == XST_SUCCESS &&
        XIicPs_SetSClk(&power_iic, E06_I2C_CLOCK_HZ) == XST_SUCCESS;
    temperature_ready = sc &&
        XSysMonPsu_CfgInitialize(&sysmon, sc, sc->BaseAddress) == XST_SUCCESS;
    if (power_ready) {
        for (size_t i = 0; i < sizeof(rails) / sizeof(rails[0]); ++i) {
            int status = E06_ERR_SENSOR;
            for (int attempt = 0; attempt < E06_I2C_RETRIES && status != E06_OK; ++attempt)
                status = identify(&rails[i]);
            if (status != E06_OK) probes_ok = 0;
        }
    }
    if (!power_ready || !probes_ok || !temperature_ready)
        return fail(E06_ERR_SENSOR, "I2C/INA226 or SysMon initialization failed");
    last_error = "";
    return E06_OK;
}

int e06_telemetry_sample(e06_telemetry_t *out) {
    XTime ticks;
    if (!out) return fail(E06_ERR_ARGUMENT, "null telemetry result");
    memset(out, 0, sizeof(*out));
    out->monitored_power_uW = INT64_MIN;
    out->temperature_mC = INT32_MIN;
    if (!initialized) return fail(E06_ERR_INIT, "telemetry is not initialized");
    XTime_GetTime(&ticks);
    out->timestamp_ticks = (uint64_t)ticks;
    if (power_ready) {
        int all_valid = 1;
        int64_t total = 0;
        for (size_t i = 0; i < sizeof(rails) / sizeof(rails[0]); ++i) {
            int64_t power;
            if (read_power(&rails[i], &power) == E06_OK) total += power;
            else all_valid = 0;
        }
        if (all_valid) { out->monitored_power_uW = total; out->power_valid = 1; }
    }
    if (temperature_ready) {
        uint16_t raw = XSysMonPsu_GetAdcData(&sysmon, XSM_CH_TEMP, XSYSMON_PS);
        /* This BSP read has no error return. Reject invalid/saturated codes and
         * implausible conversions; freshness cannot be established by this API. */
        if (raw != 0u && raw != UINT16_MAX) {
            float temperature = XSysMonPsu_RawToTemperature_OnChip(raw);
            if (isfinite(temperature) && temperature >= -55.0f && temperature <= 150.0f) {
                out->temperature_mC = (int32_t)(temperature * 1000.0f);
                out->temperature_valid = 1;
            }
        }
    }
    if (!out->power_valid || !out->temperature_valid)
        return fail(E06_ERR_SENSOR, !out->power_valid && !out->temperature_valid
            ? "power and temperature unavailable" : !out->power_valid
            ? "monitored power unavailable/incomplete" : "temperature unavailable");
    last_error = "";
    return E06_OK;
}
