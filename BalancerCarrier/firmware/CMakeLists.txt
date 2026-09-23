cmake_minimum_required(VERSION 3.16)
# No display: esp_lcd is unused, and xtensa GCC 14.2.0 (toolchain 20241119) segfaults compiling
# its esp_lcd_panel_rgb.c at -Og on this toolchain, which fails the whole build.
set(EXCLUDE_COMPONENTS esp_lcd)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(BalancerREF)
