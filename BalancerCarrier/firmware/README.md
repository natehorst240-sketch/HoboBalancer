# BalancerREF ESP32-S3 firmware

Bench-test firmware for the **BalancerREF Rev B reference puck**, ESP32-S3-MINI-1-N8, 8 MB flash, no PSRAM. It is separate from the full analyzer project. The schematic and PCB files are not changed by this firmware project. No aircraft weight corrections are automatically calculated or applied.

Implemented: MR-VERT magnetic tach, TR-VERT optical tach/emitter, all three IIS3DWB axes over SPI, hardware timestamps, finite and continuous back-to-back acquisitions, autonomous in-flight logging with GPS tagging and tach/button-wake deep sleep, approximate 1/rev velocity magnitude and phase, stability flags, run trends, BLE, native USB JSON console, persistent per-profile settings, and MicroVib comparison proposals. Wi-Fi is never initialized.

The code can check signal consistency but cannot certify IPS accuracy. Physical sampling latency, sensor frequency response, tach integrity, BLE operation, power behavior, and comparison with calibrated equipment remain hardware acceptance tests. Default gain is 1 and phase offset is 0. The provisional Z axis must be explicitly confirmed or changed before a run is marked stable.

## Hardware support status

The BQ24075 charger **is** driven, as of schematic Rev F. `board.hpp` carries the
four pins (`chgEn1`, `chgEn2`, `pgood`, `chgStat`), `tests/check_pinmap.py` verifies
them against the KiCad pin audit, and `setupCharger()` runs at boot:

- **Input current limit is set to USB500 at boot.** EN1/EN2 have 285 kOhm internal
  pull-downs, so the part powers up in USB100 - a 100 mA limit that has to cover
  system load *and* charge current, which an ESP32-S3 with BLE up largely consumes
  on its own. USB500 is the ceiling on purpose: 500 mA is the most a non-negotiated
  port must supply, and this board has no USB-PD or BC1.2. The resistor-programmed
  ~1.0 A setting stays a deliberate opt-in for a known wall adapter.
  SLUS810N Table 7-2 is indexed **(EN2, EN1)**, the reverse of the naming order.
- **`pgood` is the input-present signal**, and `chgStat` reports charging. Both are
  open-drain and **active low**, with 100k pull-ups on the board. `status` reports
  them as `input_present` and `charging`. `chgStat` goes high both when charging
  completes and when the charger is disabled, so it is not an input-present signal
  on its own.
- The Rev D SYS_SW-versus-BAT comparison and its divider are gone from the hardware,
  so `pgood` is the only way to detect an input. `supplyVolts()` reads the cell only
  while running on battery - while charging, OUT is driven from IN.

The rest of the firmware still targets Rev C behaviour; the sections below are
unchanged.

## Rev C hardware (firmware 0.4.0, 2026-09-09)

Firmware 0.4.0 targets schematic Rev C only. Accelerometer: ST IIS3DWB on SPI2 (GPIO14 SCK, 15 MOSI, 16 MISO, 17 CS, mode 3, 10 MHz), SPI-only per DS12569, fixed +/-16 g (see `src/accelscale.hpp`), LPF2 at ODR/10 (2.67 kHz). The sensor streams its fixed 26.667 kHz ODR into its FIFO with the watermark at 16 samples; INT1 (GPIO6) is the FIFO-threshold line and is timestamped by the same MCPWM capture channel that timestamped data-ready before. Each block is read in one 112-byte SPI transfer and averaged into a single 1666.7 Hz measurement sample whose timestamp is the capture tick minus 7.5 sample periods (the block mean). A block that is not exactly 16 entries, carries a non-accelerometer tag, or is read more than 500 us late is discarded and counted, so a missed interrupt shows up as a sample gap rather than a wrong number. The boxcar average adds 0.28 ms of deterministic delay (about 0.7 degrees at 390 RPM), the same class as the old LIS2DW12 filter lag and absorbed by the same calibration. Emitter GPIO9 is a 20 kHz, 10 percent LEDC PWM when the TR-VERT profile is active and 0 otherwise; the receiver's synchronous detector uses the same pulse. The IIS3DWB has no wake-on-motion, so deep sleep wakes on EXT1 when MAG_TACH (GPIO7) or the acquire button (GPIO10) pulses low; the optical profile has no wake source while its emitter is off, which is fine because flight logging uses MR-VERT. The vendored driver is `vendor/iis3dwb_reg.c` (see UPSTREAM.txt); the LIS2DW12 driver is gone.

## Build and flash

Pinned platform: PlatformIO `espressif32@6.12.0`, ESP-IDF 5.5 family. The DevKitC N8 board definition supplies the matching processor/flash configuration; actual GPIOs are explicitly set for this custom schematic in `src/board.hpp`. DIO flash is selected conservatively. The unmodified ST driver is vendored at a recorded commit with its license.

From this directory, using Python 3.11:

```powershell
python -m pip install platformio==6.1.18
python -m platformio run
python -m platformio run --target upload --upload-port COM5
```

Firmware 0.4.0-reference compiles cleanly with this pinned toolchain (verified 2026-09-07, PlatformIO 6.1.18 from `../.venv-firmware`; 698 kB image). Earlier source had never been compiled and carried three warnings-as-errors and one driver signature mismatch, all fixed without changing behavior. `tools/package_release.py` copies the images and a manifest into `release/`.

Replace COM5 with the puck's native USB port. On first flash: switch ON, hold BOOT, press/release RESET, release BOOT, then upload. Reset once after flashing if it remains in download mode. GPIO19/20 are native USB D-/D+; BOOT is GPIO0. Rev B can power/program from USB with no battery. Charging is handled by hardware regardless of firmware or switch position. Firmware has no charger STAT input and cannot report charge completion.

Do not flash a whole merged image over an existing board if you intend to preserve its settings without first reviewing the image's NVS region. Normal PlatformIO upload leaves the NVS partition intact. No device has been flashed during development here.

## Controls

- Short acquire-button press: start a timed run; during a run, cancel it. Cancelled results are explicitly invalid.
- Hold acquire for two seconds while idle: switch MR-VERT/TR-VERT and save the profile. A hold during acquisition does not change profile.
- MR-VERT: optical emitter OFF; magnetic conditioner leading **falling** edge.
- TR-VERT: optical emitter ON, including idle; optical comparator **rising** edge as reflection pulls OPT_RAW down.
- One selected edge per revolution is assumed. Multiple teeth, multiple tape patches, or extra reflections must be corrected at the test setup; automatic harmonics identification is not implemented.
- LED: 2 Hz blink acquiring; solid after a stable run; fast blink for fault/poor quality; short periodic pulse while idle (faster heartbeat when BLE connected).

Sensor/sampling runs continuously so each acquisition begins with an already settled filter. A profile or configuration change requires idle state. The optical emitter follows the selected profile, so use MR-VERT or switch OFF when finished testing to conserve battery.

## USB or BLE commands

USB uses UTF-8 JSON, one object per newline, 115200 nominal baud. BLE advertises **BalancerREF** using Nordic UART Service:

| Function | UUID |
|---|---|
| Service | `6e400001-b5a3-f393-e0a9-e50e24dcca9e` |
| RX: write with response | `6e400002-b5a3-f393-e0a9-e50e24dcca9e` |
| TX: subscribe to notifications | `6e400003-b5a3-f393-e0a9-e50e24dcca9e` |

Each BLE write contains one complete JSON command, at most 255 bytes. Negotiate a sufficient MTU or use a client supporting long writes; small commands work at the default MTU. Results are fragmented to the negotiated MTU, at most 180 bytes per notification, and end with newline. Reassemble bytes through newline before decoding JSON; discard malformed/truncated lines. A dropped line is not a measurement. Disconnecting does not stop acquisition, but notifications are not replayed; `history` retains the last 20 stable results per profile in RAM. Settings persist across reboot, history does not. BLE has no pairing/authentication in this bench revision and accepts commands from its one connected client.

```json
{"cmd":"status"}
{"cmd":"profile","value":"TR-VERT"}
{"cmd":"config","axis":"Z","sign":1}
{"cmd":"start"}
{"cmd":"start","continuous":true}
{"cmd":"stop"}
{"cmd":"history"}
```

### Continuous acquisition

`{"cmd":"start","continuous":true}` acquires back to back: each `duration_s` window ends with a `result` and the next window begins immediately, with no settling gap because sampling never stops. Every result and status carries `continuous` and a `sequence` counter (1 for the first window of a session) so a client can detect a missed notification. Each window is an independent coherent average over its own revolutions; nothing is averaged across windows, and only stable windows enter `history`. The session ends on `stop`, on a short acquire-button press, or if the sensor fails; `stop` cancels the window in progress and returns it as a final result flagged `2048` (cancelled, invalid). Configuration, profile and history commands are refused for the whole session, exactly as during a single run. A single `start` without the flag behaves as before.

Select X/Y/Z only after matching package/PCB orientation to vertical. The `sign` setting maps the chosen sensor direction to positive up. A static orientation check can establish sign; it does not calibrate dynamic IPS or chart phase.

Configuration updates affect only the active profile, are checked before application, and commit atomically through NVS. A failed save keeps the prior active configuration. Unknown/duplicate keys, nonfinite numbers, and out-of-range values are rejected. Supplying `axis` explicitly confirms it. Configuration changes clear that profile's RAM history to avoid comparing incompatible settings.

| Key | Default | Accepted values |
|---|---:|---|
| `axis` | Z, unconfirmed | X, Y, Z |
| `sign` | +1 | +1 or -1 |
| `gain` | 1 | 0.1–10 |
| `phase_direction` | +1 | +1 or -1 |
| `phase_offset_deg` | 0 | -360–360 |
| `duration_s` | 12 | 6–30 |
| `min_rpm` | 120 | at least 120, below max_rpm |
| `max_rpm` | 6000 | at most 6000, above min_rpm |

Limit the RPM range to the test regime where a saved calibration was established. A constant phase offset is not assumed valid over all speeds. Configuration values are user-entered transforms, not evidence of calibrated accuracy.

## What IPS and phase mean here

The IIS3DWB runs at its fixed **26.667 kHz ODR, fixed +/-16 g, LPF2 ODR/10**, decimated by 16 in firmware to **1666.7 Hz** measurement samples (see the Rev C hardware section). Full scale, batch rate and FIFO mode are read back after configuration. SPI at 10 MHz.

The range is fixed at +/-16 g and never switched during a session, so no run can mix differently scaled samples. DS12569 states noise density is independent of full scale; at 0.488 mg/LSB the step is about 1/28 of the ~3.9 mg RMS per-sample noise, so the wide range costs no usable resolution (0.08 IPS at 300 RPM is ~6.5 mg peak). Clipping is judged on every raw FIFO sample before the 16-sample average, at 95% of full scale because LPF2 can round a saturated peak slightly low, and is tracked per axis. The per-revolution fit models DC and 1..4/rev together so strong 2/rev content does not leak into the 1/rev vector. Each tach edge is held until the first sample at or after it arrives, because a block's mean timestamp can precede an edge that was delivered first.

The two tachs and the FIFO-watermark line are captured by three channels of one MCPWM capture timer. ISR code only queues timestamps. A priority-22 task reads the sensor; analysis and USB/BLE use separate lower-priority tasks. Delayed sensor reads (>500 microseconds after the ISR timestamp), queue overflows, missing samples, and read failures invalidate the acquisition. Hardware timestamps do not remove the accelerometer's internal filter delay or an interrupt serviced too late; both are bench checks.

For each complete revolution, each axis is least-squares fitted to `DC + C*cos(theta) + S*sin(theta)` using sample angles interpolated between the actual bounding tach edges. DC/gravity is retained separately. This extracts the synchronous **1/rev component**, not overall broadband vibration. The three axes remain separate; vertical is not an XYZ vector magnitude.

For sinusoidal 1/rev motion, `velocity_peak = acceleration_peak / (2*pi*RPM/60)`. Acceleration is converted from g to inches/s². Velocity coefficients are integrated with the corresponding 90-degree phase shift. Peak IPS and RMS IPS are both output; for this fitted sinusoid RMS=peak/sqrt(2). There is no assumed MicroVib peak/RMS convention.

**Raw phase** means degrees of elapsed rotation from the selected tach edge to the positive velocity peak, increasing with time: `v(theta)=Vpeak*cos(theta-phase)`. It is not automatically a clock position on the manufacturer's balance chart. Signed acceleration phase is also included to distinguish acceleration and velocity conventions.

The adjusted outputs apply:

```
ips_peak = raw_axis_ips_peak * gain
ips_rms = ips_peak / sqrt(2)
signed_phase = wrap(raw_axis_velocity_phase + (sign < 0 ? 180 : 0))
adjusted_phase = wrap(phase_direction * signed_phase + phase_offset_deg)
```

Raw XYZ magnitudes/phases remain unchanged in every result. No 30-degree or two-o'clock geometric correction is silently inserted. Your provided rotor/weight information is preserved in `config/tail-rotor-reference.json` as user-supplied metadata for future reference visualization; it is not compiled into a correction algorithm.

## Reading quality flags

`valid` means no detected hard acquisition fault, not calibrated accuracy. `stable` additionally requires confirmed axis, period CV <=2%, and reasonably consistent per-revolution vibration vectors. `phase_valid` additionally requires a usable amplitude. `quality` summarizes the result:

- `stable_vector` (`phase_valid`): amplitude and phase both repeat. Only these runs feed run-to-run delta and the `compare` calibration.
- `direction_only` (`direction_valid` but not `stable`): phase repeats per revolution but amplitude varies (flag 128 without 4096). The phase is published for a rough correction; the amplitude must not be used for calibration or a final acceptance decision.
- `unreliable`: a hard fault (including selected-axis overrange), bad tach, unconfirmed axis, weak signal, or inconsistent angle (flag 4096). The adjusted phase is JSON null.

`raw_amplitude_scatter_ips_peak` and `per_rev_phase_scatter_deg` split `raw_vector_scatter_ips_peak` into its along-vector and across-vector parts. Each axis in `raw_axes` reports `clipped`; clipping on an unused axis is reported but does not invalidate the run. Raw values remain available for diagnosis and must be considered together with the flags.

| Bit | Meaning |
|---:|---|
| 1 | Missing/stale/out-of-range tach |
| 2 | Fewer than 8 usable complete revolutions |
| 4 | Sample gap, inconsistent sample count, or buffer capacity exceeded |
| 8 | Selected axis reached 95% of +/-16 g on any raw sample, including gravity (message: overrange) |
| 16 | Sensor I2C error |
| 32 | Capture or sample queue overflow |
| 64 | RPM period variation >2% |
| 128 | Vibration vector scatter (amplitude and phase combined) >20% of coherent amplitude, with 0.005 IPS floor |
| 256 | Weak phase: amplitude below 0.005 IPS or insufficient relative to measured vector scatter |
| 512 | Vertical axis not explicitly confirmed |
| 1024 | Late sample read, invalid time ordering, or degenerate fit |
| 2048 | Run cancelled |
| 4096 | Phase unstable: across-vector per-revolution scatter >20% of coherent amplitude (about 11 degrees), with 0.005 IPS floor |

Scatter is a repeatability metric, not a calibrated noise floor or statistical accuracy interval. There is no universal accept/reject balancing threshold. A periodic interference or extra tach pattern can be consistent yet wrong. The +/-16 g range includes static gravity: a clipped selected axis always invalidates the run and is never reported as a lower IPS result. Run-to-run delta is provided only for stable runs within 2% RPM under the same profile settings; the operator must also maintain the same physical mounting.

## In-flight logging (flight mode)

`{"cmd":"flight","value":true}` turns the puck into an autonomous logger; the setting persists and survives sleep. On every boot or wake in flight mode it starts continuous acquisition on the active profile, tags each window with the latest GPS fix, appends one terse JSON line per window to the `storage` SPIFFS partition (about 4.9 MB, roughly 16,000 windows), and never overwrites: once the partition passes 95 percent it stops recording and `status` reports `log.full`. BLE is not started in flight mode. The acquire button is inert; hold it two seconds to change profile only while idle. `{"cmd":"flight","value":false}` returns to bench behaviour (BLE comes back after a reboot).

**USB rules.** A USB data connection pauses autonomous acquisition and blocks sleep so the puck can be commanded and downloaded; unplugging resumes. A plain charger does not enumerate and does not pause it.

**Sleep.** After 3 minutes without a tach edge (and at least 3 minutes awake) the puck sends the GPS to backup mode, powers the IIS3DWB down and enters deep sleep armed on EXT1 (MAG_TACH GPIO7 or the acquire button GPIO10 going low). Rotor spin-up on the magnetic pickup or a button press wakes it; handling alone does not. The LM1815 stays powered, so sleep current is dominated by it (a few mA); budget about 260 mAh for a day of two flight hours plus eight dormant hours. Wake cause is written as a `boot` record and shown in `status.wake`.

**Level-flight gate.** Each record carries `lvl`, true only when the window was `stable`, at least 3 valid fixes arrived, mean ground speed was at least 2 m/s, speed spread was at most 1.5 m/s, circular course spread at most 10 degrees, and the sign-adjusted vertical DC was within 6 percent of 1 g. Turns, climbs, descents, hover and ground runs therefore log with `lvl:false` and can be filtered out. GPS gives ground speed, not airspeed; fly reciprocal headings if wind matters.

**Record format**, one line each, raw uncalibrated values:

```json
{"type":"log","seq":12,"run":40,"t":"2026-09-07T18:02:11Z","up":812345,"prof":"MR-VERT","ax":"Z","sg":1,"v":true,"s":true,"pv":true,"f":0,"rpm":388.20,"cv":0.0031,"m":[0.0120,0.0210,0.2345],"p":[10.0,20.0,123.4],"dc":[0.010,-0.020,0.998],"sc":0.0120,"fix":true,"lat":40.123456,"lon":-111.123456,"gs":20.30,"crs":84.0,"alt":1400.0,"sat":9,"lvl":true,"nfix":6,"gsm":20.30,"gss":0.60,"css":2.1}
{"type":"boot","t":null,"up":15,"note":"wake:motion"}
```

`m`/`p`/`dc` are per-axis X, Y, Z peak IPS, velocity phase in degrees and DC in g; `sc` is vector scatter; `gsm`/`gss`/`css` are the gate's mean speed, speed spread and course spread; `t` is GPS UTC or null before a fix. Flags `f` are the same bits as bench results.

**Download and erase.** `{"cmd":"download"}` streams `download_begin`, every stored line unchanged, then `download_end` with `complete` and the record count; a truncated last line from a power loss is skipped. `{"cmd":"erase"}` deletes the log and is never implied by a download. Both are refused while acquiring, so in flight mode plug in USB first. From the laptop:

```powershell
python tools/puck.py --port COM5 --flight on
python tools/puck.py --port COM5 --download flight.jsonl
python tools/puck.py --port COM5 --erase
```

The tool refuses to report success, and tells you not to erase, if the received count differs from the puck's.

**GPS.** J4 on the schematic: UART1, GPIO1 TX to module RX, GPIO2 RX from module TX, GPIO13 PPS (wired, unused by firmware), 3.3 V, 8N1 NMEA. The reader auto-detects 38400 (u-blox M10/F10 default) or 9600 (Quectel L76-K, u-blox M8) by cycling every 4 s until checksum-valid sentences arrive; `status.gps.baud` shows the rate in use. Sleep sends both UBX-RXM-PMREQ (u-blox backup, wake on UART) and `$PMTK161,0` (Quectel standby, wake on any byte); each vendor ignores the other. Candidate modules: u-blox NEO-F10N (Digi-Key 672-NEO-F10N-00B-TR-ND is the bare LCC module and needs a carrier with an L1/L5 antenna path; the SparkFun NEO-F10N breakout is the drop-in form) or Quectel L76-K (2.7-3.4 V, internal LNA, passive patch antenna, about 25 mA tracking, roughly 0.5 mA in standby; the Waveshare L76K breakout brings out VCC/GND/TX/RX/PPS). RMC and GGA from any talker are parsed with checksum verification; `status.gps` reports presence, fix, satellites, speed and rejected sentences. Backup mode uses UBX-RXM-PMREQ and wakes on UART activity, which the firmware sends at boot; a non-u-blox module will simply ignore the sleep request and keep drawing its normal current. PPS is not used yet.

Nothing in this mode has run on hardware. Bench checks before trusting a flight log: GPS sentences appear in `status`, a window logs with a plausible `t`, sleep entry and motion wake, resume after USB unplug, and that `lvl` goes false when the puck is carried around by hand.

## MicroVib comparison and logging

Install the host tool dependencies in a virtual environment, then:

```powershell
python -m pip install -r tools/requirements.txt
python tools/puck.py --port COM5 --command '{"cmd":"config","axis":"Z","sign":1}'
python tools/puck.py --port COM5 --profile TR-VERT --acquire --log tail-runs.jsonl
python tools/puck.py --ble --profile MR-VERT --acquire --log main-runs.jsonl
python tools/puck.py --ble --acquire --continuous --runs 10 --log series.jsonl
```

`--continuous` collects `--runs` results (0 = until Ctrl+C) and then sends `stop`, logging the final cancelled partial as well.

The logger appends UTC receipt times around the untouched firmware objects. `tools/comparison-template.csv` records the reference instrument, mounting, tach, installed weights, RPM, and amplitude convention alongside a puck run. Pair measurements under matching conditions and repeat at multiple amplitudes/speeds. Do not assume two physically separate sensor mounts have identical response.

After a stable run, a reference comparison can propose a transform without applying it:

```json
{"cmd":"compare","reference_ips_peak":0.25,"reference_phase_deg":120}
```

These numbers are examples, not measured results. Enter peak IPS (convert RMS for the 1/rev sinusoid if necessary). A proposal reports `gain = reference_peak / raw_selected_peak` and the phase difference under the selected axis/sign/direction convention. Verify multiple paired measurements; then apply a chosen transform explicitly with `config`. A reference comparison does not establish a weight influence coefficient or authorize a maintenance balancing correction. A persistent opposite angle direction requires `phase_direction`, not merely a constant phase offset.

## Verification and first hardware checks

`tests/run_host_tests.sh` compiles and runs the exact firmware DSP code on a Linux host with GCC, AddressSanitizer and UndefinedBehaviorSanitizer. On this Windows workstation it runs under WSL. Tests cover synthetic velocity/phase recovery, DC and 2/rev rejection, raw/calibrated separation, sign/direction, timer rollover, missing samples/tach, glitches, clipping, weak signal, amplitude variation and RPM endpoints. A raw-path generator feeds int16 samples at the full 26.667 kHz ODR (gravity, 2/3-rev harmonics, datasheet noise, quantization and rail saturation) through the same `decodeBlock` and `Measurement` code across 300/500/1900/2200 RPM and 0.08/0.5/2.0 IPS, plus overrange, single-sample impacts on used and unused axes, and phase wander. `tools/sim.sh` runs the same raw-path generator (`tests/rawsim.hpp`) as a bench simulator, so vibration cases can be tried before live runs. With no arguments it runs every preset (clean, main-rotor minimum, tail-rotor maximum, heavy 2/rev, overrange, impacts, amplitude and phase wander, RPM drift, tach jitter/dropout/glitch, sample gap, weak signal, extra noise, unconfirmed axis) and checks each against its expected quality; `list` shows presets and settings; a preset name and/or `key=value` settings print one full result, e.g. `wsl sh tools/sim.sh rpm=390 ips=0.8 h2=1.2 tach_jitter=100`. It exercises the measurement code only, not task timing, SPI or the tach front end.

`tests/test_tools.py` checks fragmented transport parsing and logger protocol behavior.

Before useful rotor comparison, verify: sensor initialization and static XYZ sign; regular 1666.7 Hz FIFO-block interrupts and sub-500 us block reads with BLE active; known tach pulse frequency and single edge per revolution; injected vibration magnitude/phase over the intended RPM range; optical polarity and magnetic leading edge; button/LED operation; USB/BLE disconnects; retained settings after reset. Keep the mounting axis and measurement convention in every comparison record. No physical prototype results are claimed by software tests.

Source references: [ST IIS3DWB datasheet](https://www.st.com/resource/en/datasheet/iis3dwb.pdf), [ST driver repository](https://github.com/STMicroelectronics/iis3dwb-pid), [Espressif MCPWM capture](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32s3/api-reference/peripherals/mcpwm.html), [Espressif NimBLE](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32s3/api-reference/bluetooth/nimble/index.html). Upstream driver license/commit are included under `vendor/`.
