cmake_minimum_required(VERSION 3.16)
# Unlike the carrier, this project needs esp_lcd (the RGB panel driver). The carrier excludes
# it because xtensa GCC 14.2.0 segfaulted on esp_lcd_panel_rgb.c at -Og; tests/toolchain-check
# records what this toolchain does with it.
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(BalancerDisplay)
