#!/bin/sh
# Host tests for the display firmware's ESP-independent code. Same approach as the carrier:
# the exact files that ship are compiled with GCC and both sanitizers and run on the host.
set -eu
cd "$(dirname "$0")/.."
mkdir -p build
g++ -std=c++17 -O2 -Wall -Wextra -Werror -fsanitize=undefined,address -fno-omit-frame-pointer \
    -Isrc -Ivendor src/protocol.cpp vendor/cJSON.c tests/test_protocol.cpp -o build/test_protocol
./build/test_protocol
