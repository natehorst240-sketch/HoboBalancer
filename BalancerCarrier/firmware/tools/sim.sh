#!/bin/sh
# Build and run the host vibration simulator (see tools/sim.cpp). On Windows run it under WSL:
#   wsl sh tools/sim.sh [preset] [key=value ...]
set -eu
cd "$(dirname "$0")/.."
mkdir -p build
if [ ! -x build/sim ] || [ -n "$(find src/measurement.cpp src/measurement.hpp src/accelscale.hpp tests/rawsim.hpp tools/sim.cpp -newer build/sim)" ]; then
    g++ -std=c++17 -O2 -Wall -Wextra -Werror -Isrc -Itests src/measurement.cpp tools/sim.cpp -o build/sim
fi
exec ./build/sim "$@"
