# BalancerREF (HOBOVibe) — reference rotor-vibration puck

ESP32-S3 firmware is in [firmware/README.md](firmware/README.md), including build/flash instructions, MR-VERT/TR-VERT controls, BLE/USB protocol, and a MicroVib comparison logger. Its measurement accuracy remains subject to bench validation.

Open **BalancerREF.kicad_pro**, then **BalancerREF.kicad_sch**, in KiCad 10.0.3 or later (KiCad 10 format; KiCad 9 will not open it). One A2 schematic sheet, Rev F (2026-09-13), hand-laid-out in KiCad (title "HOBOVibe Hobby Helicopter Dynamic Balancer"). The PCB is 50 x 50 mm, four layers (In1 GND plane, In2 +3V3 plane), routed except `SYS`, `SYS_SW`, `BAT` and `USB_VBUS`, which were pulled off the +3V3 plane layer on 2026-09-18 and need re-routing on the outer layers. The custom library and project library table travel with the schematic. Most symbols are standard KiCad 10 symbols; IIS3DWB, SN74LVC1G123, LM1815, TS3021 and BQ24075RGT have local definitions with pin mappings verified against the manufacturer tables (see DATASHEET-VERIFICATION.md). The embedded USB-C receptacle and potentiometer symbols were re-synced from the KiCad 10 library (`scripts/sync_kicad10_symbols.py`) because KiCad 10 renamed the USB-C shield pin and footprint pad from S1 to SH; the pre-sync project is archived in `archives/RevB-before-kicad10-symbol-sync-20260907-214948.zip`.

This is a reference/troubleshooting instrument for approximate RPM, 1/rev vibration magnitude, phase, stability and trends. Maintenance balancing remains with calibrated MicroVib/DynaVibe equipment. Firmware and physical performance have not been validated by schematic ERC.

## Review files

- `review/BalancerREF.pdf`: searchable vector rendering of the one-sheet schematic.
- `review/erc.rpt`: KiCad 10 ERC report, all severities included.
- `review/connectivity-check.txt`: independent exact-net comparison against the intended circuits.
- `review/IC-pin-audit.csv`: every IC physical pad, manufacturer function, resulting net and unused-pin explanation.
- `review/pin-net-connections.csv`: all component pin/net connections.
- `review/unused-pins.json`: reasons for every NC marker.
- `DATASHEET-VERIFICATION.md`: manufacturer sources, pinout decisions and calculations.

All local functional circuits use real wires. Labels carry signals between complete blocks. Test points stay beside their measured circuits. Ground symbols all represent the same common ground.

## Operating intent

| Profile | Tach input | IR emitter | Vibration |
|---|---|---|---|
| MR-VERT | External isolated two-wire VR pickup at J3 / J_MAG | Off | Internal IIS3DWB on SPI, all axes available |
| TR-VERT | Onboard pulsed-red synchronous-detection optical tach (retroreflective tape) | 20 kHz pulses | Same sensor |

### Rev F changes (2026-09-13)

Rev F is the **repo-review revision**: no new function, but several things that had to
be right before any copper is routed. Every claim was checked against the manufacturer
source, and two of them did not survive that check (see DATASHEET-VERIFICATION.md for
the full record, including what was deliberately NOT changed).

- **PD1 polarity corrected - the optical tach could never have worked.** The detector
  was wired cathode to +3V3 and anode to the transimpedance summing node. Reverse bias
  is correct that way, which is why it survived this long, but photocurrent leaves the
  ANODE, so it was injected into the summing node instead of pulled out of it. The
  inverting TIA then drove TIA_OUT down, the inverting second stage drove OPT_AMP UP
  from its 1.65 V idle, and U4 has OPT_AMP on IN- against a 1.016 V threshold on IN+.
  The comparator input sat 634 mV above the threshold and light pushed it further away,
  so the output never left its low state and TR-VERT had no tach at all. Cathode now
  goes to PD_TIA_IN and the anode to GND: same 1.65 V reverse bias, but TIA_OUT rises,
  OPT_AMP falls through the threshold, and the 470k hysteresis works as drawn. About
  5.3 uA of photocurrent trips it. Bonus: the emitter turn-off edge, which lands inside
  the gate window and cannot be rejected, now couples into the summing node in the
  non-detection direction - which matters because this revision also moved Q1 nearer
  PD1.
- **R18 3.0 -> 3.9 ohm on the head board.** The emitter runs from SYS_SW, and the
  BQ24075 regulates OUT to 5.5 V, so the old value gave about 1.1 A peak into D1's 1 A
  absolute maximum. The BOM note had only checked the 4.2 V battery case. This is a
  regression introduced by Rev E: the Schottky it removed had been holding SYS near
  4.55 V. 3.9 ohm keeps the 500 mA design point at a full cell and lands at about
  0.90 A worst case.
- **U9 SN74LVC1G08 -> SN74LVC1G132.** R29/C26 fed the AND gate a 0.47 us edge against a
  10 ns/V input transition spec. The 1G132 is a Schmitt NAND on the identical SOT-23-5
  pinout, so the footprint is untouched, and it conditions both inputs rather than only
  the RC branch. It inverts, so U10's trigger moved from B rising to ~A falling - the
  SN74LVC1G123 supports both edges.
- **Switching loop off the vias.** L1 and C4-C7 were on the back with U6 on the front,
  so a 2.4 MHz switching node and both its input and output caps reached the IC through
  vias. They moved to U6's face, and C1/C2/C3/C30 followed for the BQ24075. The
  "ICs front, passives back" rule does not survive contact with a switching converter.
  Two follow-on corrections came out of review: aim at the **pin**, not the net, and
  place the fastest part first. U6 pins 5-8 are all on SYS_SW, so targeting "the input
  net" had put the caps next to EN and PS/SYNC - logic inputs that happen to be strapped
  high - rather than VIN and VINA; and the 10u bulk had taken the close spot while the
  100n sat 4.4 mm out. C5 now sits 2.07 mm from VINA and C4 2.68 mm from VIN. C1, the
  100n bypass on the BQ24075's IN pin, turned out to be **24 mm away on the back of the
  board**, which is the same as not fitting it; it is now 5.3 mm out on the front.
  TP6 and TP10 were squatting immediately left of U6 - the side VIN and PGND are on -
  and were the reason the bulk input cap could not get near its pins. They moved beside
  the circuits they actually probe.
- **U1 decoupling at the pad.** C8 is now 0.38 mm from the 3V3 pad rather than about
  9 mm. Both caps stay on the back, since U1's body owns that part of the front.
- **Head board loop and TIA.** C20/R18/Q1 now cluster in 6.9 x 3.3 mm instead of
  spanning the board width, and R21/C21 moved from 4 mm off Q1 to 16 mm, sitting
  3.6/3.9 mm from U8 pins 1 and 2. The remaining ~8 mm up to D1 is set by its
  provisional lens keepout, which is why those parts sat at the board edges to begin
  with.
- **Firmware drives the charger.** EN1/EN2 were left to their internal pulldowns, so the
  input limit sat at USB100 - 100 mA covering system load and charge current together.
  `setupCharger()` selects USB500 at boot and status reports `input_present`/`charging`.
- Accepted rather than fixed, both recorded with numbers: SW1's 300 mA switching rating
  against a ~180 mA steady draw with larger transients, and the LM1815's 3.6 mA on the
  always-on rail making deep sleep a milliamp affair.

The head board is **Rev B** as of this revision - its first change since creation.

### Rev E changes (2026-09-13)

- **BQ24075 replaces the MCP73831 charger**, and D2, Q3, R27 and R31 go with it. The
  discrete Schottky-plus-PFET arrangement OR-ed USB against the battery; the BQ24075
  has an integrated dynamic power path (DPPM) that does it properly - system and
  charging powered independently, operation with a defective or absent cell, USB-IF
  inrush limiting, and VIN-DPM so a weak port sags instead of collapsing. Support
  parts: R3 3.57k sets ~249 mA fast charge (about 0.5C for a 500 mAh cell), R35 1.6k
  sets the ~1.0 A resistor-programmed input limit, R36 10k stands in for the absent
  pack thermistor on TS, R37/R38 100k pull up the open-drain status pins, C30 10 uF on
  OUT. TMR is deliberately left open for the default safety timers; CE and SYSOFF are
  tied low. All seventeen pins are checked against SLUS810N in DATASHEET-VERIFICATION.md.
- **Charger control on four GPIOs**: EN1 = GPIO5, EN2 = GPIO18, PGOOD = GPIO21,
  CHG = GPIO38. Note that the datasheet's current-limit table is indexed (EN2, EN1),
  the reverse of the naming order. Both EN pins have 285k internal pulldowns, so the
  part powers up in USB100 (100 mA). *Rev F added `setupCharger()`, which selects
  USB500 at boot; before that, firmware never drove these and the puck charged at
  100 mA - a limit that covers system load and charge current together.*
- **BAT sense divider removed**: R33, R34, C31 and the `BAT_SENSE` net are gone. They
  existed only to infer USB presence by comparing SYS_SW against BAT. PGOOD reports a
  valid input source directly from the device that arbitrates it, which is both simpler
  and more trustworthy, and dropping the divider retires a 500k ADC source impedance
  and a ~2 uA permanent drain on the cell. GPIO4 is an unused pin again.
  The trade is that `SUPPLY_SENSE` (GPIO12, ADC2_CH1) is now the board's only supply
  measurement, and ADC2 is the unit shared with the radio - which is precisely why the
  removed divider had been put on ADC1.
- **Wire stubs swept**: the optical split, SW4, R5 and the charger swap each left the
  wires that used to reach the deleted pins, connected to a live net at one end and to
  nothing at the other - 19 of them, plus one orphaned no-connect flag. 23 wires were
  removed and 2 were trimmed back to the label they carry (`BAT` and `OPT_LED_EN`,
  where deleting the wire would have taken the label with it). `scripts/fix_dangling_wires.py`
  exports the netlist before and after and refuses to keep any edit that moves a single
  pin to a different net. **ERC is now 0 errors and 0 warnings**, down from 20.
- **`/SYS` added to the Power net class** (0.50 mm). It is the BQ24075's OUT rail and
  carries the entire system load; it did not exist under the old topology and would
  otherwise have routed at the 0.20 mm default, rated 0.74 A.

**At Rev E firmware did not drive the charger.** `board.hpp` carried the four pins and
`tests/check_pinmap.py` verified them against the KiCad pad audit, but nothing read
PGOOD or raised the input current limit. Rev F fixed that - see the Rev F section
above.

### Rev D changes (2026-09-13)

- **BAT sense divider added** *(removed again in Rev E - the BQ24075's PGOOD pin
  reports input power directly)*: R33/R34 (1M) and C31 (100n) put `BAT/2` on GPIO4
  (ADC1_CH3) as `BAT_SENSE`. `SUPPLY_SENSE` alone cannot distinguish USB from battery
  because SYS is fed either from USB through D2 or from the cell through Q3, and the
  ranges overlap - a USB port at the low end of spec minus D2's drop sits near 4.30 V
  against a full cell at 4.20 V, inside divider tolerance plus ADC error. Comparing the
  two separates them: `SYS_SW > BAT + ~0.3 V` means USB present. 1M/1M rather than
  SUPPLY_SENSE's 100k/100k because this divider hangs on the cell even when the puck is
  switched off (~2 uA against ~21 uA); the resulting 500k source impedance means
  firmware must use a long sample time and multisample.
- **Optical front end split out** to `BalancerREF_OptHead` (2026-09-11), leaving J5, a
  7-way cable connector. D1/PD1 have no leads to form, so they need their own copper on
  the bracket's second leg. The cut sits after the comparator so the cable carries only
  DC rails and digital edges.
- **SW4 (RESET) removed**: SW1 feeds U6's VIN and EN, so the power slide already
  power-cycles the MCU. R4/C10/TP13 still hold EN high and keep it probeable.
- **R5 removed**: it duplicated R9's 10k BOOT pull-up on the same net. The BOOT net is
  now U1.4, R9.2, SW3.2, TP14.1.
- Board work: 50 x 50 mm four-layer, M2.5 corner mounting holes, fiducials on both
  faces, `UP`/`LEFT` orientation silkscreen, and net classes for track widths.

**Firmware 0.4.0 predates this revision.** It never gained a `BAT_SENSE` reader, which
Rev E made moot. The pin-map test no longer passes vacuously: it now asserts that every
pin in `board.hpp` is covered by the test.

### Rev C changes (2026-09-09)

- **Accelerometer**: LIS2DW12 (I2C) replaced by the ST IIS3DWB vibration sensor on 4-wire SPI: GPIO14 SCK, GPIO15 MOSI, GPIO16 MISO, GPIO17 CS, INT1 data-ready still on GPIO6. RES pads 2/3 to GND, 10/11 open, per DS12569. The IIS3DWB has no wake-on-motion, so deep-sleep wake moves to EXT1 on MAG_TACH (GPIO7) or the acquire button (GPIO10). Firmware 0.3.0 still targets the LIS2DW12 and needs the driver port before this revision is flashed.
- **Optical tach**: the DC infrared pair and trimpot are gone. D1 is a Cree XP-E2 red LED pulsed at 20 kHz / 5 us / about 500 mA from SYS_SW through Q1 (3 ohm 1206 series, 100 uF local reservoir). PD1 BPW34S is reverse-biased into a 10k transimpedance stage referenced to 1.65 V (U8A), then a x12 inverting AC stage (U8B, TLV9062). In the detection row, U4 TS3021 compares against a fixed 1.03 V threshold with 470k hysteresis, U9 (74LVC1G08) accepts a hit only while the RC-delayed emitter pulse is high (synchronous detection), and U10 (74LVC1G123, 100k / 1 nF, about 100 us retriggerable) stretches consecutive hits into one OPT_TACH edge per tape pass. Working range 18-24 in with retroreflective tape and the Ledil TINA lens; see PhotoTach-BOM.csv for the Digi-Key sourced parts. Threshold and delay values are bench-set.
- **Battery**: Q4 AO3401A between J2 and the BAT node blocks a reversed pack (gate to GND; body diode conducts at first contact, then the channel).
- **USB**: D3 SMF5.0A TVS on VBUS at the connector.
- **ADC**: 100 nF on SUPPLY_SENSE at GPIO12.
- **GPS header J4** (added 2026-09-07) unchanged.
- The Rev C circuits were first produced by `scripts/build_schematic.py` (Rev B generator retained as `build_schematic_revb.py`, transformation in `patch_rev_c.py`) followed by `scripts/add_gps.py`, then the sheet was re-laid-out by hand in KiCad on 2026-09-09 into five blocks on A2 with the same connectivity (verified identical net membership). The generators are now guarded and refuse to run without `--overwrite-hand-layout`; the schematic file is the source of truth. Rev B final state archived in `archives/RevB-final-before-revc-20260909-030859.zip`.

J4 is a 1x05 2.54 mm header for an optional 3.3 V u-blox class GPS module used only by the in-flight logging mode: 1 VCC, 2 GND, 3 GPS TX to GPIO2 (UART1 RX), 4 GPS RX from GPIO1 (UART1 TX), 5 PPS to GPIO13. UART1 was chosen over the UART0 pads so ROM boot output never reaches the GPS. Added 2026-09-07 with `scripts/add_gps.py`; the pre-GPS project is archived in `archives/RevB-before-gps-20260907-230803.zip`.

J3 is two plated wire holes, not an aircraft connector: pin 1 MAG+, pin 2 MAG-. Its final hole spacing/strain relief is a PCB decision. The mating aircraft connector belongs on the external twisted-pair pigtail. MAG- is common ground; this front end is for a passive, isolated pickup, not an energized aircraft signal.

The 500 mAh battery must be a protected single-cell 4.2 V-charge LiPo pack. J2 pin 1 is positive; pin 2 is negative. Confirm the pack's JST polarity before connection. The PCB charger is not an overdischarge/protection circuit.

Revision B charges with SW1 either ON or OFF, at approximately 249 mA nominal. D2 and Q3 provide USB/battery power sharing: USB supplies the puck separately from the charger, allowing normal charge termination while running. SW1 is after the combined SYS rail and controls only the puck. Without USB, the battery automatically supplies SYS through Q3. With USB and SW1 ON, programming can work without a battery; hold BOOT while resetting if needed. Use a regulated 5 V USB source rated at least 1 A. This revision has no USB current-negotiated charging controller; unrestricted operation from a legacy computer port is not established.

The GPIO12 divider now measures switched supply voltage (`SUPPLY_SENSE = SYS_SW / 2`), rather than directly sensing USB VBUS. This prevents the divider from feeding an unpowered MCU with SW1 OFF. It is not a dedicated USB-presence signal. The original revision is preserved in `archives/RevA-before-independent-charging.zip`. Use `BalancerREF-Schematic-RevC.pdf` for the current preview; older RevB PDFs may still be open in a viewer.

The optical tach is modelled on an industrial retroreflective photoelectric sensor: pulsed emitter, synchronous detection, fixed threshold. Ambient light cannot coincide with the 5 us emitter windows, so sunlight and flickering lighting are rejected rather than trimmed out. A red acrylic window and an internal baffle between D1 and PD1 are still required. Insufficient reflection must produce an invalid measurement, not a balancing recommendation.

## GPIO allocation

| Signal | ESP32 GPIO | MINI-1 physical pad |
|---|---:|---:|
| ACCEL_SCK | 14 | 18 |
| ACCEL_MOSI | 15 | 19 |
| ACCEL_MISO | 16 | 20 |
| ACCEL_CS | 17 | 21 |
| ACCEL_DRDY | 6 | 10 |
| MAG_TACH | 7 | 11 |
| OPT_TACH | 8 | 12 |
| OPT_LED_EN (20 kHz PWM, emitter) | 9 | 13 |
| ACQUIRE_BUTTON | 10 | 14 |
| STATUS_LED | 11 | 15 |
| SUPPLY_SENSE | 12 | 16 |
| USB D- | 19 | 23 |
| USB D+ | 20 | 24 |
| GPS_UART_TX (to GPS RX, J4.4) | 1 | 5 |
| GPS_UART_RX (from GPS TX, J4.3) | 2 | 6 |
| GPS_PPS (J4.5) | 13 | 17 |
| BOOT | 0 | 4 |
| EN / RESET | — | 45 |

Use GPIO-matrix routing to MCPWM capture or RMT for tach timing. Keep Wi-Fi disabled during normal BLE acquisition. Sample the IIS3DWB at its fixed 26.7 kHz ODR (or decimate in firmware) and timestamp INT1 data-ready; its response is flat to 6.3 kHz so filter phase at rotor frequencies is negligible. Account for sensor/filter and optical delays when estimating phase. There is no hardware absolute-phase calibration.

## Scope before PCB (historical, written before Rev D; the PCB now exists)

Future target is approximately 50 × 40 mm. Place MEMS near the rigid mounting point, reserve the Espressif antenna keepout, and point the formed-lead optical parts through the LEFT edge. No board outline, copper, routing or PCB file is included. Inductor, formed-lead optics, switches and wire-hole footprints are intentionally left for mechanical selection in the PCB phase; IC footprints and the USB/JST connectors use library assignments.

Bench verification must establish useful pickup amplitude/range, optical working distance and ambient tolerance, RPM/phase repeatability, vibration noise floor and power/charging behavior. ERC checks wiring classes and connectivity; it does not establish measurement accuracy or EMC performance.

## Reproduce verification

The scripts use Python 3 with `sexpdata` and `pymupdf`, and an installed KiCad 10 symbol library. `build_schematic.py` is retired (guarded) because the sheet is hand-maintained; `final_review.py` runs the whole chain below on the current file and refreshes the review PNGs, hashes and PDF copies.

```powershell
& 'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe' sch erc BalancerREF.kicad_sch -o review/erc.rpt --severity-all --exit-code-violations
& 'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe' sch export netlist BalancerREF.kicad_sch -o review/BalancerREF.net
python scripts/verify_netlist.py
& 'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe' sch export pdf BalancerREF.kicad_sch -o review/BalancerREF.pdf
```

The verifier checks complete net membership, not just that expected pairs connect. This catches unintended shorts, bypassed series components and supply capacitors accidentally attached to switching nodes. No ERC exclusions or severity downgrades are used. Three PWR_FLAG symbols identify USB input power, common source ground and power arriving through SW1. The regulator and charger outputs already declare their own power sources.
