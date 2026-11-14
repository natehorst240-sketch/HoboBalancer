#include "display.hpp"
#include "board.hpp"
#include <cstring>
extern "C" {
#include "driver/gpio.h"
#include "esp_heap_caps.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_panel_rgb.h"
#include "esp_log.h"
}

namespace {
const char *TAG = "display";
esp_lcd_panel_handle_t panel = nullptr;
uint16_t *line = nullptr;  // one row, for fill()
}  // namespace

namespace display {
bool begin() {
    // Fully qualified on purpose: inside namespace display, `width`, `height` and `backlight`
    // name this file's functions, so a using-directive would pick the wrong thing.
    namespace P = board::panel;
    esp_lcd_rgb_panel_config_t cfg{};
    cfg.clk_src = LCD_CLK_SRC_DEFAULT;
    cfg.timings.pclk_hz = P::pclkHz;
    cfg.timings.h_res = P::width; cfg.timings.v_res = P::height;
    cfg.timings.hsync_pulse_width = P::hsyncPulse; cfg.timings.hsync_back_porch = P::hsyncBackPorch; cfg.timings.hsync_front_porch = P::hsyncFrontPorch;
    cfg.timings.vsync_pulse_width = P::vsyncPulse; cfg.timings.vsync_back_porch = P::vsyncBackPorch; cfg.timings.vsync_front_porch = P::vsyncFrontPorch;
    cfg.timings.flags.pclk_active_neg = P::pclkActiveNeg;
    cfg.timings.flags.hsync_idle_low = P::hsyncIdleLow; cfg.timings.flags.vsync_idle_low = P::vsyncIdleLow;
    cfg.data_width = 16; cfg.bits_per_pixel = 16;
    cfg.num_fbs = 1;                      // one full frame in PSRAM (480x272x2 = 261 KB)
    cfg.dma_burst_size = 64;              // IDF 5.5 name; psram_trans_align is deprecated
    cfg.hsync_gpio_num = P::hsync; cfg.vsync_gpio_num = P::vsync; cfg.de_gpio_num = P::de; cfg.pclk_gpio_num = P::pclk;
    cfg.disp_gpio_num = -1;
    // RGB565 on the 16-bit bus: B0..B4, G0..G5, R0..R4 in data lines 0..15.
    const int order[16] = {P::b[0], P::b[1], P::b[2], P::b[3], P::b[4], P::g[0], P::g[1], P::g[2], P::g[3], P::g[4], P::g[5], P::r[0], P::r[1], P::r[2], P::r[3], P::r[4]};
    for (int i = 0; i < 16; ++i) cfg.data_gpio_nums[i] = order[i];
    cfg.flags.fb_in_psram = 1;
    if (esp_lcd_new_rgb_panel(&cfg, &panel) != ESP_OK) { ESP_LOGE(TAG, "rgb panel create failed"); return false; }
    if (esp_lcd_panel_reset(panel) != ESP_OK || esp_lcd_panel_init(panel) != ESP_OK) { ESP_LOGE(TAG, "panel init failed"); return false; }
    line = static_cast<uint16_t *>(heap_caps_malloc(size_t(P::width) * sizeof(uint16_t), MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL));
    if (!line) return false;
    gpio_config_t bl{};
    bl.pin_bit_mask = 1ULL << P::backlight; bl.mode = GPIO_MODE_OUTPUT;
    gpio_config(&bl);
    fill(0);
    display::backlight(true);
    ESP_LOGI(TAG, "%s %dx%d up", board::name, P::width, P::height);
    return true;
}
int width() { return board::panel::width; }
int height() { return board::panel::height; }
bool draw(int x1, int y1, int x2, int y2, const uint16_t *pixels) {
    return panel && esp_lcd_panel_draw_bitmap(panel, x1, y1, x2 + 1, y2 + 1, pixels) == ESP_OK;
}
void fill(uint16_t c) {
    if (!panel || !line) return;
    for (int x = 0; x < board::panel::width; ++x) line[x] = c;
    for (int y = 0; y < board::panel::height; ++y) esp_lcd_panel_draw_bitmap(panel, 0, y, board::panel::width, y + 1, line);
}
void backlight(bool on) { gpio_set_level(gpio_num_t(board::panel::backlight), on ? 1 : 0); }
}  // namespace display
