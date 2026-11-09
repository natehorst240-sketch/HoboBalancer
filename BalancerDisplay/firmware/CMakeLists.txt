cmake_minimum_required(VERSION 3.16)
# Unlike the carrier, this project needs esp_lcd (the RGB panel driver). The carrier excludes
# it because xtensa GCC 14.2.0 once segfaulted on esp_lcd_panel_rgb.c at -Og. Checked
# 2026-11-09 on Linux with espressif32@6.12.0 (ESP-IDF 5.5.0, xtensa-esp-elf-gcc
# 14.2.0_20241119, CONFIG_COMPILER_OPTIMIZATION_DEBUG): the file compiles and the project
# links. If that crash returns on another machine, build this component at -O2 instead.
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(BalancerDisplay)
