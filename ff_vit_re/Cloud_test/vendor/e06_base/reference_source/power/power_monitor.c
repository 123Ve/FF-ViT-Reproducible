#include "power_monitor.h"

#include "power_math.h"
#include "xparameters.h"
#include "xstatus.h"

#define E06_I2C_MUX_ADDRESS 0x75u
#define E06_I2C_CLOCK_HZ 400000u
#define E06_MUX_ENABLE 0x04u
#define E06_INA226_REG_SHUNT 0x01u
#define E06_INA226_REG_BUS 0x02u
#define E06_INA226_REG_MANUFACTURER 0xfeu
#define E06_INA226_REG_DIE 0xffu
#define E06_I2C_RETRIES 3

const PowerRail e06_power_rails[] = {
    {"VCCPSINTFP", POWER_DOMAIN_PS, 0x40u, 5000u},
    {"VCCPSINTLP", POWER_DOMAIN_PS, 0x41u, 5000u},
    {"VCCPSAUX", POWER_DOMAIN_PS, 0x42u, 5000u},
    {"VCCPSPLL", POWER_DOMAIN_PS, 0x43u, 5000u},
    {"MGTRAVCC", POWER_DOMAIN_PS, 0x44u, 5000u},
    {"MGTRAVTT", POWER_DOMAIN_PS, 0x45u, 5000u},
    {"VCCO_PSDDR_504", POWER_DOMAIN_PS, 0x46u, 5000u},
    {"VCCOPS", POWER_DOMAIN_PS, 0x47u, 5000u},
    {"VCCOPS3", POWER_DOMAIN_PS, 0x4au, 5000u},
    {"VCCPSDDRPLL", POWER_DOMAIN_PS, 0x4bu, 5000u},
    {"VCCINT", POWER_DOMAIN_PL, 0x40u, 2000u},
    {"VCCBRAM", POWER_DOMAIN_PL, 0x41u, 5000u},
    {"VCCAUX", POWER_DOMAIN_PL, 0x42u, 5000u},
    {"VCC1V2", POWER_DOMAIN_PL, 0x43u, 5000u},
    {"VCC3V3", POWER_DOMAIN_PL, 0x44u, 5000u},
    {"VADJ_FMC", POWER_DOMAIN_PL, 0x45u, 5000u},
    {"MGTAVCC", POWER_DOMAIN_PL, 0x46u, 5000u},
    {"MGTAVTT", POWER_DOMAIN_PL, 0x47u, 5000u},
};

const size_t e06_power_rail_count = sizeof(e06_power_rails) / sizeof(e06_power_rails[0]);

static int wait_idle(XIicPs *iic) {
    unsigned int remaining = 1000000u;
    while (XIicPs_BusIsBusy(iic) && remaining != 0u) --remaining;
    return remaining != 0u ? XST_SUCCESS : XST_FAILURE;
}

static int select_domain(XIicPs *iic, PowerDomain domain) {
    uint8_t command = (uint8_t)(E06_MUX_ENABLE | (uint8_t)domain);
    if (XIicPs_MasterSendPolled(iic, &command, 1, E06_I2C_MUX_ADDRESS) != XST_SUCCESS)
        return XST_FAILURE;
    return wait_idle(iic);
}

static int read_register(XIicPs *iic, uint8_t address, uint8_t reg, uint16_t *value) {
    uint8_t bytes[2] = {0u, 0u};
    if (XIicPs_MasterSendPolled(iic, &reg, 1, address) != XST_SUCCESS)
        return XST_FAILURE;
    if (wait_idle(iic) != XST_SUCCESS) return XST_FAILURE;
    if (XIicPs_MasterRecvPolled(iic, bytes, 2, address) != XST_SUCCESS)
        return XST_FAILURE;
    if (wait_idle(iic) != XST_SUCCESS) return XST_FAILURE;
    *value = (uint16_t)(((uint16_t)bytes[0] << 8) | bytes[1]);
    return XST_SUCCESS;
}

static int identify(XIicPs *iic, const PowerRail *rail) {
    uint16_t manufacturer = 0u;
    uint16_t die = 0u;
    if (select_domain(iic, rail->domain) != XST_SUCCESS) return XST_FAILURE;
    if (read_register(iic, rail->address, E06_INA226_REG_MANUFACTURER, &manufacturer) != XST_SUCCESS)
        return XST_FAILURE;
    if (read_register(iic, rail->address, E06_INA226_REG_DIE, &die) != XST_SUCCESS)
        return XST_FAILURE;
    return manufacturer == INA226_MANUFACTURER_ID &&
                   (die & 0xfff0u) == INA226_DIE_ID
               ? XST_SUCCESS
               : XST_FAILURE;
}

int power_monitor_initialize(XIicPs *iic) {
    XIicPs_Config *config = XIicPs_LookupConfig(XPAR_XIICPS_0_BASEADDR);
    if (config == NULL) return XST_FAILURE;
    if (XIicPs_CfgInitialize(iic, config, config->BaseAddress) != XST_SUCCESS)
        return XST_FAILURE;
    if (XIicPs_SelfTest(iic) != XST_SUCCESS) return XST_FAILURE;
    return XIicPs_SetSClk(iic, E06_I2C_CLOCK_HZ);
}

int power_monitor_probe_all(XIicPs *iic) {
    for (size_t index = 0; index < e06_power_rail_count; ++index) {
        int ok = XST_FAILURE;
        for (int attempt = 0; attempt < E06_I2C_RETRIES && ok != XST_SUCCESS; ++attempt)
            ok = identify(iic, &e06_power_rails[index]);
        if (ok != XST_SUCCESS) return XST_FAILURE;
    }
    return XST_SUCCESS;
}

int power_monitor_read(XIicPs *iic, const PowerRail *rail, PowerReading *reading) {
    uint16_t shunt = 0u;
    uint16_t bus = 0u;
    for (int attempt = 0; attempt < E06_I2C_RETRIES; ++attempt) {
        if (identify(iic, rail) == XST_SUCCESS &&
            read_register(iic, rail->address, E06_INA226_REG_SHUNT, &shunt) == XST_SUCCESS &&
            read_register(iic, rail->address, E06_INA226_REG_BUS, &bus) == XST_SUCCESS) {
            reading->bus_raw = bus;
            reading->shunt_raw = (int16_t)shunt;
            reading->bus_uV = ina226_bus_uV(bus);
            reading->current_uA = ina226_current_uA((int16_t)shunt, rail->shunt_uohm);
            reading->power_uW = ina226_power_uW(reading->bus_uV, reading->current_uA);
            return XST_SUCCESS;
        }
    }
    return XST_FAILURE;
}

const char *power_domain_name(PowerDomain domain) {
    return domain == POWER_DOMAIN_PS ? "PS" : "PL";
}
