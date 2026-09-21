#include "fuelgauge.hpp"
#include "board.hpp"
#include <cmath>
extern "C" {
#include "driver/gpio.h"
#include "driver/i2c_master.h"
#include "esp_log.h"
}

namespace {
constexpr char TAG[] = "fuelgauge";

// ---------------------------------------------------------------------------
// !! UNVERIFIED AGAINST THE DATASHEET !!
// These register numbers and scale factors were written from memory: the Analog
// Devices server timed out repeatedly while fetching MAX17048-MAX17049.pdf on
// 2026-09-21, so nothing below has been read off the document. Everything else in
// this port was checked against a datasheet; this block was not.
//
// Check these five constants before trusting any reading, then delete this comment:
//   the 7-bit I2C address, the three register numbers, and the two scale factors.
// A wrong scale factor will not fail loudly - it will report a plausible but wrong
// battery voltage, which is worse than no reading at all.
constexpr uint8_t ADDR       = 0x36;      // 7-bit
constexpr uint8_t REG_VCELL  = 0x02;      // 16-bit, big endian
constexpr uint8_t REG_SOC    = 0x04;      // 16-bit, big endian
constexpr uint8_t REG_CRATE  = 0x16;      // 16-bit, big endian, SIGNED
constexpr double  VCELL_LSB_V     = 78.125e-6;  // volts per LSB
constexpr double  SOC_LSB_PERCENT = 1.0 / 256.0;
constexpr double  CRATE_LSB_PCT_H = 0.208;      // percent per hour per LSB
// ---------------------------------------------------------------------------

// Above this the cell is gaining charge. Left well clear of zero so gauge noise and
// slow self-discharge do not flip the flag while idle.
constexpr double CHARGING_THRESHOLD_PCT_H = 0.5;

i2c_master_bus_handle_t bus = nullptr;
i2c_master_dev_handle_t dev = nullptr;
bool ready = false;

// Reads one 16-bit big-endian register. Returns false and leaves `out` untouched on
// any failure, including a gauge that never came up.
bool read16(uint8_t reg, uint16_t &out) {
    if (!ready) return false;
    uint8_t rx[2] = {0, 0};
    if (i2c_master_transmit_receive(dev, &reg, 1, rx, sizeof rx, 100) != ESP_OK) return false;
    out = uint16_t(rx[0]) << 8 | rx[1];
    return true;
}
}  // namespace

namespace fuelgauge {

bool setup() {
    i2c_master_bus_config_t bc = {};
    bc.i2c_port = I2C_NUM_0;
    bc.sda_io_num = gpio_num_t(board::i2cSda);
    bc.scl_io_num = gpio_num_t(board::i2cScl);
    bc.clk_source = I2C_CLK_SRC_DEFAULT;
    bc.glitch_ignore_cnt = 7;
    // The module already fits 10k pull-ups on both lines; adding internal ones would
    // only weaken the edges.
    bc.flags.enable_internal_pullup = false;
    if (i2c_new_master_bus(&bc, &bus) != ESP_OK) {
        ESP_LOGW(TAG, "I2C bus init failed; battery reporting disabled");
        return false;
    }
    if (i2c_master_probe(bus, ADDR, 100) != ESP_OK) {
        ESP_LOGW(TAG, "no MAX17048 at 0x%02X; battery reporting disabled", ADDR);
        return false;
    }
    i2c_device_config_t dc = {};
    dc.dev_addr_length = I2C_ADDR_BIT_LEN_7;
    dc.device_address = ADDR;
    dc.scl_speed_hz = 400000;
    if (i2c_master_bus_add_device(bus, &dc, &dev) != ESP_OK) {
        ESP_LOGW(TAG, "could not add MAX17048; battery reporting disabled");
        return false;
    }
    ready = true;
    ESP_LOGI(TAG, "MAX17048 found at 0x%02X", ADDR);
    return true;
}

bool present() { return ready; }

double cellVolts() {
    uint16_t raw;
    if (!read16(REG_VCELL, raw)) return NAN;
    return raw * VCELL_LSB_V;
}

double stateOfCharge() {
    uint16_t raw;
    if (!read16(REG_SOC, raw)) return NAN;
    return raw * SOC_LSB_PERCENT;
}

double chargeRate() {
    uint16_t raw;
    if (!read16(REG_CRATE, raw)) return NAN;
    return int16_t(raw) * CRATE_LSB_PCT_H;   // signed: negative while discharging
}

bool charging() {
    const double r = chargeRate();
    return !std::isnan(r) && r > CHARGING_THRESHOLD_PCT_H;
}

}  // namespace fuelgauge
