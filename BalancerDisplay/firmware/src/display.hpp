#pragma once
#include <cstdint>

// Panel bring-up through esp_lcd. Pins and timing come from board.hpp only. Exposes a frame
// buffer in PSRAM plus a flush so a renderer (LVGL later) can draw; nothing here knows what is
// drawn.
namespace display {
bool begin();                                  // panel on, backlight on; false on any driver error
int width();
int height();
// Copy an RGB565 rectangle into the panel. Blocking; x2/y2 are inclusive, like esp_lcd.
bool draw(int x1, int y1, int x2, int y2, const uint16_t *pixels);
void fill(uint16_t rgb565);                    // whole screen; used by the bring-up test
void backlight(bool on);
}  // namespace display
