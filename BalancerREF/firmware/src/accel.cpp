#include "accel.hpp"
#include "board.hpp"
#include "iis3dwb_reg.h"
#include <cstring>
extern "C" {
#include "driver/spi_master.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
}

namespace {
spi_device_handle_t device = nullptr;
stmdev_ctx_t ctx{};
bool ready = false;
constexpr uint8_t readBit = 0x80;
constexpr unsigned maxDrain = 4 * accel::decimation;
alignas(4) iis3dwb_fifo_out_raw_t fifoBuffer[maxDrain];  // DMA target: word aligned, 7*16 = 112 bytes

// ST SPI framing: one address byte (bit 7 = read) followed by the data bytes; IF_INC auto-increments.
int32_t busWrite(void *, uint8_t reg, const uint8_t *buf, uint16_t len) {
    spi_transaction_t t{};
    t.addr = reg & 0x7F;
    t.length = size_t(len) * 8;
    t.tx_buffer = buf;
    return spi_device_polling_transmit(device, &t) == ESP_OK ? 0 : -1;
}
int32_t busRead(void *, uint8_t reg, uint8_t *buf, uint16_t len) {
    spi_transaction_t t{};
    t.addr = reg | readBit;
    t.length = size_t(len) * 8;
    t.rxlength = size_t(len) * 8;
    t.rx_buffer = buf;
    return spi_device_polling_transmit(device, &t) == ESP_OK ? 0 : -1;
}
void delayMs(uint32_t ms) { vTaskDelay(pdMS_TO_TICKS(ms ? ms : 1)); }
}  // namespace

namespace accel {
bool setup() {
    spi_bus_config_t bus{};
    bus.mosi_io_num = board::accelMosi; bus.miso_io_num = board::accelMiso; bus.sclk_io_num = board::accelSck;
    bus.quadwp_io_num = -1; bus.quadhd_io_num = -1; bus.max_transfer_sz = int(sizeof(fifoBuffer)) + 8;
    if (spi_bus_initialize(SPI2_HOST, &bus, SPI_DMA_CH_AUTO) != ESP_OK) return false;
    spi_device_interface_config_t dev{};
    dev.command_bits = 0; dev.address_bits = 8; dev.mode = 3; dev.clock_speed_hz = 10 * 1000 * 1000;
    dev.spics_io_num = board::accelCs; dev.queue_size = 2;
    if (spi_bus_add_device(SPI2_HOST, &dev, &device) != ESP_OK) return false;
    ctx.write_reg = busWrite; ctx.read_reg = busRead; ctx.mdelay = delayMs;
    uint8_t id = 0;
    if (iis3dwb_device_id_get(&ctx, &id) || id != IIS3DWB_ID) return false;
    if (iis3dwb_reset_set(&ctx, 1)) return false;
    uint8_t rst = 1;
    for (int i = 0; i < 50 && rst; ++i) { vTaskDelay(pdMS_TO_TICKS(2)); if (iis3dwb_reset_get(&ctx, &rst)) return false; }
    if (rst) return false;
    // SPI only (DS12569: I2C cannot sustain the data rate), 2 g, LPF2 at ODR/10, FIFO streaming in blocks.
    if (iis3dwb_i2c_interface_set(&ctx, IIS3DWB_I2C_DISABLE) || iis3dwb_block_data_update_set(&ctx, 1) ||
        iis3dwb_auto_increment_set(&ctx, 1) || iis3dwb_xl_full_scale_set(&ctx, IIS3DWB_2g) ||
        iis3dwb_xl_filt_path_on_out_set(&ctx, IIS3DWB_LP_ODR_DIV_10) ||
        iis3dwb_fifo_watermark_set(&ctx, decimation) || iis3dwb_fifo_xl_batch_set(&ctx, IIS3DWB_XL_BATCHED_AT_26k7Hz) ||
        iis3dwb_fifo_mode_set(&ctx, IIS3DWB_STREAM_MODE)) return false;
    iis3dwb_pin_int_route_t route{};
    route.fifo_th = 1;
    if (iis3dwb_pin_int1_route_set(&ctx, &route)) return false;
    if (iis3dwb_xl_data_rate_set(&ctx, IIS3DWB_XL_ODR_OFF)) return false;
    // Read back the configuration we depend on rather than trusting the writes.
    iis3dwb_fs_xl_t fs; iis3dwb_bdr_xl_t bdr; iis3dwb_fifo_mode_t mode;
    if (iis3dwb_xl_full_scale_get(&ctx, &fs) || iis3dwb_fifo_xl_batch_get(&ctx, &bdr) || iis3dwb_fifo_mode_get(&ctx, &mode)) return false;
    ready = fs == IIS3DWB_2g && bdr == IIS3DWB_XL_BATCHED_AT_26k7Hz && mode == IIS3DWB_STREAM_MODE;
    return ready;
}

bool start() {
    if (!ready) return false;
    // Flush anything batched while idle so the first watermark is a clean block.
    if (iis3dwb_fifo_mode_set(&ctx, IIS3DWB_BYPASS_MODE) || iis3dwb_fifo_mode_set(&ctx, IIS3DWB_STREAM_MODE)) return false;
    if (iis3dwb_xl_data_rate_set(&ctx, IIS3DWB_XL_ODR_26k7Hz)) return false;
    iis3dwb_odr_xl_t odr;
    return !iis3dwb_xl_data_rate_get(&ctx, &odr) && odr == IIS3DWB_XL_ODR_26k7Hz;
}

void powerDown() {
    if (!ready) return;
    iis3dwb_xl_data_rate_set(&ctx, IIS3DWB_XL_ODR_OFF);
    iis3dwb_fifo_mode_set(&ctx, IIS3DWB_BYPASS_MODE);
}

bool readBlock(float g[3], unsigned &entries) {
    entries = 0;
    if (!ready) return false;
    uint16_t level = 0;
    if (iis3dwb_fifo_data_level_get(&ctx, &level)) return false;
    entries = level;
    if (level < decimation) return false;
    const unsigned n = level > maxDrain ? maxDrain : level;
    if (iis3dwb_fifo_out_multi_raw_get(&ctx, fifoBuffer, uint16_t(n))) return false;
    // One block per interrupt: any other count means an interrupt was missed or the FIFO ran ahead.
    if (n != decimation) return false;
    double sum[3] = {0, 0, 0};
    for (unsigned i = 0; i < n; ++i) {
        if ((fifoBuffer[i].tag >> 3) != IIS3DWB_XL_TAG) return false;
        for (int a = 0; a < 3; ++a) {
            const int16_t raw = int16_t(uint16_t(fifoBuffer[i].data[2 * a]) | (uint16_t(fifoBuffer[i].data[2 * a + 1]) << 8));
            sum[a] += iis3dwb_from_fs2g_to_mg(raw);
        }
    }
    for (int a = 0; a < 3; ++a) g[a] = float(sum[a] / n * 0.001);
    return true;
}

bool present() { return ready; }
}  // namespace accel
