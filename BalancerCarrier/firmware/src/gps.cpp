#include "gps.hpp"
#include "board.hpp"
#include <atomic>
#include <cstring>
extern "C" {
#include "driver/uart.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
}

namespace {
constexpr uart_port_t port = UART_NUM_1;
// Vendor-agnostic: u-blox M10/F10 ship at 38400, Quectel L76-K and u-blox M8 at 9600.
// The reader cycles through these until checksum-valid sentences arrive.
constexpr int bauds[] = {38400, 9600};
constexpr int64_t autobaudUs = 4000000;
portMUX_TYPE lock = portMUX_INITIALIZER_UNLOCKED;
flight::Fix latestFix;
std::atomic<uint32_t> sequence{0}, sentenceCount{0}, rejectCount{0};
std::atomic<int64_t> lastValidUs{0};
std::atomic<int> activeBaud{bauds[0]};
bool started = false;

void reader(void *) {
    flight::Nmea nmea;
    uint8_t bytes[128];
    unsigned baudIndex = 0;
    int64_t lastSwitch = esp_timer_get_time();
    for (;;) {
        const int n = uart_read_bytes(port, bytes, sizeof(bytes), pdMS_TO_TICKS(100));
        for (int i = 0; i < n; ++i) {
            if (!nmea.feed(char(bytes[i]))) continue;
            portENTER_CRITICAL(&lock);
            latestFix = nmea.fix();
            portEXIT_CRITICAL(&lock);
            // Only RMC is new motion data for the gate; any valid sentence proves the baud rate.
            sequence = nmea.motionSequence();
            lastValidUs = esp_timer_get_time();
        }
        sentenceCount = nmea.sentences();
        rejectCount = nmea.rejected();
        const int64_t now = esp_timer_get_time();
        const int64_t sinceValid = lastValidUs ? now - lastValidUs : now;
        if (sinceValid > autobaudUs && now - lastSwitch > autobaudUs) {
            baudIndex = (baudIndex + 1) % (sizeof(bauds) / sizeof(bauds[0]));
            uart_set_baudrate(port, bauds[baudIndex]);
            uart_flush_input(port);
            activeBaud = bauds[baudIndex];
            lastSwitch = now;
        }
    }
}

void send(const uint8_t *data, size_t len) {
    uart_write_bytes(port, data, len);
    uart_wait_tx_done(port, pdMS_TO_TICKS(100));
}

// UBX frame: sync, class, id, length LE, payload, Fletcher-8 checksum over class..payload.
void ubx(uint8_t cls, uint8_t id, const uint8_t *payload, uint16_t len) {
    uint8_t frame[64];
    if (len + 8 > sizeof(frame)) return;
    frame[0] = 0xB5; frame[1] = 0x62; frame[2] = cls; frame[3] = id;
    frame[4] = uint8_t(len & 0xFF); frame[5] = uint8_t(len >> 8);
    std::memcpy(frame + 6, payload, len);
    uint8_t a = 0, b = 0;
    for (int i = 2; i < 6 + len; ++i) { a = uint8_t(a + frame[i]); b = uint8_t(b + a); }
    frame[6 + len] = a; frame[7 + len] = b;
    send(frame, 8 + len);
}
}  // namespace

namespace gps {
void start() {
    if (started) return;
    uart_config_t cfg{};
    cfg.baud_rate = bauds[0]; cfg.data_bits = UART_DATA_8_BITS; cfg.parity = UART_PARITY_DISABLE;
    cfg.stop_bits = UART_STOP_BITS_1; cfg.flow_ctrl = UART_HW_FLOWCTRL_DISABLE; cfg.source_clk = UART_SCLK_DEFAULT;
    if (uart_driver_install(port, 1024, 0, 0, nullptr, 0) != ESP_OK) return;
    if (uart_param_config(port, &cfg) != ESP_OK) return;
    if (uart_set_pin(port, board::gpsTx, board::gpsRx, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE) != ESP_OK) return;
    // A module left in standby by an earlier sleep wakes on any RX activity (u-blox and Quectel alike).
    const uint8_t wake = 0xFF;
    send(&wake, 1);
    started = xTaskCreatePinnedToCore(reader, "gps", 4096, nullptr, 5, nullptr, 1) == pdPASS;
}

flight::Fix latest() {
    flight::Fix f;
    portENTER_CRITICAL(&lock);
    f = latestFix;
    portEXIT_CRITICAL(&lock);
    return f;
}
uint32_t fixSequence() { return sequence; }
uint32_t sentences() { return sentenceCount; }
uint32_t rejected() { return rejectCount; }
int baud() { return activeBaud; }
bool present() { return lastValidUs && esp_timer_get_time() - lastValidUs < 5000000; }

void sleep() {
    if (!started) return;
    // u-blox: UBX-RXM-PMREQ (16-byte payload): duration 0 = until wake, flags backup, wakeupSources uartrx.
    uint8_t payload[16]{};
    payload[8] = 0x02;
    payload[12] = 0x08;
    ubx(0x02, 0x41, payload, sizeof(payload));
    // Quectel L76 family: standby mode, exits on any UART byte. Each vendor ignores the other's message.
    static const char pmtk[] = "$PMTK161,0*28\r\n";
    send(reinterpret_cast<const uint8_t *>(pmtk), sizeof(pmtk) - 1);
}
}  // namespace gps
