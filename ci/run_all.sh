#!/bin/sh
# Every host-runnable check in the repository, in one place, so CI and a developer run the same
# thing. Exits non-zero on the first failure. Needs: g++, python3, node, and for the browser
# tests playwright with Chromium (SKIP_BROWSER=1 to leave those out).
set -eu
cd "$(dirname "$0")/.."
step() { printf '\n== %s\n' "$*"; }

step "generated files must not be tracked"
if git ls-files | grep -E '(^|/)sdkconfig\.[A-Za-z0-9_-]+$|(^|/)\.pio/|(^|/)build/' | grep -v 'sdkconfig\.defaults$'; then
    echo "FAIL: generated build output is tracked (see above)"; exit 1
fi
echo ok

for fw in BalancerREF BalancerCarrier; do
    step "$fw firmware: host tests, pin map, tool tests"
    (cd "$fw/firmware" && sh tests/run_host_tests.sh && python3 tests/check_pinmap.py && python3 -m unittest -q tests.test_tools)
done

step "BalancerCarrier simulator presets"
(cd BalancerCarrier/firmware && sh tools/sim.sh | tail -1 | grep -q "matched their expected outcome" && sh tools/sim.sh | tail -1)

step "BalancerDisplay firmware: host tests"
(cd BalancerDisplay/firmware && sh tests/run_host_tests.sh)

step "solver library and DSS cross-checks"
node BalancerV2/solver/test_mv2.js
node BalancerV2/solver/test_dss_histrecs.js
python3 BalancerV2/profiles/test_decode_spc.py

if [ "${SKIP_BROWSER:-0}" = "1" ]; then
    step "browser tests skipped (SKIP_BROWSER=1)"
else
    step "solver page in headless Chromium"
    sh BalancerV2/solver/tests/run_ui_tests.sh
fi

step "ALL CHECKS PASSED"
