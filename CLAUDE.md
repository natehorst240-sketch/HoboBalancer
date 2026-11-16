# Working rules for this repository

These come from review rounds where fixes were reported done and were not. They apply to every
change, by anyone.

1. **Reproduce before fixing.** A reported defect gets a failing test first, committed with the
   fix. The test must fail on the parent commit and pass on the fix; say so in the commit message.
2. **Enumerate every path that touches the changed data.** For a data-model change (keys,
   identity, filtering, formats) list each reader and writer and check each one. The first
   calibration fix covered the key and missed solutions, learning, migration and import.
3. **Report only real exit codes.** Never pipe a build or test through a filter that hides its
   status. Quote the pass line with its check count. "Tests pass" without numbers is not a report.
4. **Verify number formats and conventions against an external reference, not against our own
   reading of a screen.** Two decoders (.SPC bins, .HST level) were wrong by powers of two for
   weeks because a float was assumed; MicroBase's own stored values exposed both. The DSS
   cross-check tests pin those values; extend them when a new field is decoded.
5. **No generated artifacts in the tree.** sdkconfig.<env>, .pio/, build/ are ignored and must stay
   untracked; CI fails if they are tracked or if a build modifies tracked files.
6. **Every claim in a doc carries its evidence.** Say where a fact came from (file, DSS page,
   measurement) and when. Correct wrong statements in place rather than appending.
7. **Hardware behaviour is not verified until it ran on hardware.** Host tests and target builds
   are necessary, not sufficient. Say what remains unverified, every time.
8. **READMEs stay short.** No elaborate READMEs; they go stale. Facts that change live next to
   the code or in the dated notes (BalancerV2/profiles/A109-procedure.md).

Run everything with `sh ci/run_all.sh` (SKIP_BROWSER=1 without Chromium). CI runs the same
script plus both ESP32-S3 target builds.
