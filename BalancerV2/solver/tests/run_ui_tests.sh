#!/bin/sh
# Browser regression tests for the solver page: drive index.html in headless Chromium through
# Playwright. Each script prints one "ok"/"FAIL" line per check and exits non-zero on failure.
# Needs node and playwright with Chromium installed (npm i -g playwright && npx playwright
# install chromium). Also run ../test_mv2.js for the library checks.
set -u
cd "$(dirname "$0")"
status=0
for t in [0-9]*.js; do
    echo "== $t"
    node "$t" || status=1
done
[ $status -eq 0 ] && echo "PASS: all browser test scripts" || echo "FAIL: see above"
exit $status
