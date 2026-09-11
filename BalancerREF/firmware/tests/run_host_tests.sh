#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p build
g++ -std=c++17 -O2 -Wall -Wextra -Werror -fsanitize=undefined,address -fno-omit-frame-pointer -Isrc src/measurement.cpp tests/test_measurement.cpp -o build/test_measurement
./build/test_measurement
g++ -std=c++17 -O2 -Wall -Wextra -Werror -fsanitize=undefined,address -fno-omit-frame-pointer -Isrc src/flightlog.cpp tests/test_flightlog.cpp -o build/test_flightlog
./build/test_flightlog
