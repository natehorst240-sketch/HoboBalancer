// BalancerDisplay bring-up. Milestone 0: panel alive (colour sweep), proving the esp_lcd RGB
// path builds and runs on this toolchain. The carrier link and the UI follow.
#include "board.hpp"
#include "display.hpp"
extern "C" {
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
}

extern "C" void app_main() {
    static const char *TAG = "main";
    if (!display::begin()) { ESP_LOGE(TAG, "display failed; check board.hpp against the panel"); vTaskDelay(portMAX_DELAY); }
    const uint16_t colours[] = {0xF800, 0x07E0, 0x001F, 0xFFFF, 0x0000};  // red, green, blue, white, black
    for (;;) for (uint16_t c : colours) { display::fill(c); vTaskDelay(pdMS_TO_TICKS(1000)); }
}
