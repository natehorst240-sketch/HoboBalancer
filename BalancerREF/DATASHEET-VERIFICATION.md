# Manufacturer pinout verification

Reviewed 2026-09-07 against the manufacturer documents below. `review/IC-pin-audit.csv` records all 118 IC pads and their actual KiCad-exported nets, including all 65 ESP32 module pads. The electrical net specification is separately checked by `scripts/verify_netlist.py`.

## U1 — Espressif ESP32-S3-MINI-1-N8

[Current manufacturer datasheet, v1.7](https://documentation.espressif.com/esp32-s3-mini-1_mini-1u_datasheet_en.pdf), pin table on pages 11–12, USB/peripheral descriptions and peripheral schematic. Original PDF saved in `sources/`.

Verified pad 3 = 3V3, 4 = GPIO0, 23 = GPIO19/USB D-, 24 = GPIO20/USB D+, 45 = EN. Ground pads are 1, 2, 42, 43 and 46–65; the normal KiCad symbol stacks these ground pins, and all are present in the exported netlist. The CSV verifies the remaining GPIO/pad mapping individually. N8 is the 8 MB flash / no PSRAM version. GPIO3/45/46 remain unloaded, preserving strap defaults.

Local 10 µF and 100 nF bypass; EN has 10 kΩ / 1 µF and reset button. GPIO0 has pull-ups and a service BOOT button. Native USB uses 22 Ω series resistors close to the MCU. VBUS detection is a 100 kΩ/100 kΩ divider to GPIO12. Normal operation uses BLE; firmware routes tach edges to capture hardware through the GPIO matrix.

## U2 — ST LIS2DW12TR

[Manufacturer datasheet DS11811 Rev 9, September 2024](https://www.st.com.cn/resource/en/datasheet/lis2dw12.pdf), pin table page 4, application figure 6/page 19. Verified through the manufacturer's current web PDF; direct local download timed out.

| Pad | Function / connection |
|---:|---|
| 1 | SCL, 4.7 kΩ pull-up |
| 2 | CS tied to VDD_IO for I2C |
| 3 | SA0 tied to ground, address 0x18 |
| 4 | SDA, 4.7 kΩ pull-up |
| 5 | Internal NC, explicitly unused |
| 6, 8 | Ground |
| 7 | Reserved: must connect to ground |
| 9 | VDD, local 100 nF plus 10 µF bulk |
| 10 | VDD_IO, local 100 nF |
| 11 | INT2 unused; retain output configuration |
| 12 | INT1 / data-ready to GPIO6 |

Both supplies use 3.3 V. Ceramic bulk is specified with adequate effective capacitance at bias. All three accelerometer axes are available over I2C. High-performance/low-noise mode and output/filter rates are firmware settings.

## U3 — TI LM1815MX/NOPB

[Manufacturer datasheet SNOSBU8F](https://www.ti.com/lit/ds/symlink/lm1815.pdf), connection diagram page 1, reference circuit figure 17/page 6 and application details pages 8–9. Original PDF saved.

Pins: 1/4/6/13 NC; 2 ground; 3 signal input; 5 mode; 7 peak storage; 8 VCC; 9 timing input; 10 gated output; 11 input select; 12 open-collector reference pulse; 14 RC timing.

3.3 V lies within the electrical-table 2.5–12 V operating range. Mode pin 5 is intentionally open for adaptive Mode 1. Pins 9/11 are grounded; pin 10 is unused. Pin 12 has a 5.6 kΩ pull-up to 3.3 V. Local 100 nF + 10 µF bypass supports the internal input clamp.

Two 10 kΩ pulse-rated series resistors give 20 kΩ; ±60 V peak produces at most approximately 3 mA into the internal clamp. This is a design envelope, not a qualified surge rating. 150 kΩ and 1 nF give 0.673RC ≈101 µs pulse width; 1.6 MΩ / 330 nF follow TI's peak-storage network. Timestamp the falling leading edge of the output pulse.

## U4 — ST TS3021IYLT

[Manufacturer datasheet DS4807 Rev 11, August 2025](https://www.st.com.cn/resource/en/datasheet/ts3021.pdf), page 2 pin table. Verified through the manufacturer's current web PDF; direct local download timed out.

SOT-23-5: 1 OUT, 2 VCC-, 3 IN+, 4 IN-, 5 VCC+. Powered from 3.3 V with local 100 nF; output is push-pull. The local symbol uses the normal comparator triangle and this pin mapping.

Phototransistor raw collector voltage feeds IN-. RV1 feeds IN+; 470 kΩ output feedback produces positive hysteresis. At mid-trim, the divider Thevenin resistance is about 4.85 kΩ; ideal hysteresis is 3.3 × 4.85/(470 + 4.85) ≈34 mV. The threshold adjusts approximately 0.8–2.5 V, with small feedback shifts. This is manually adjustable ambient thresholding, not automatic ambient subtraction.

## U5 — TI BQ24075RGT

[Manufacturer datasheet SLUS810N, September 2008 – revised October 2021](https://www.ti.com/lit/ds/symlink/bq24075.pdf), Table 7-1 (pin functions), Table 7-2 (EN1/EN2), Section 6 (device comparison table) and Section 8.5 (electrical characteristics). Original PDF saved as `sources/BQ24075.pdf`.

Package is RGT0016C, VQFN-16 3x3 mm with a thermal pad. Figure 7-3 is the BQ24075 top view; every pin below was read from it and from Table 7-1.

| Pin | Name | Net | Check against SLUS810N |
|---|---|---|---|
| 1 | TS | `/TS`, R36 10k to GND | Table 7-1: "For applications that do not use the TS function, connect a 10-kΩ fixed resistor from TS to VSS". Exactly that — there is no thermistor in the pack. |
| 2, 3 | BAT | `/BAT`, C3 10 µF | Spec asks 4.7–47 µF ceramic. C3 is 10 µF 10 V; derating at 4.2 V must leave at least 4.7 µF effective. |
| 4 | CE | GND | Active low. "Connect CE to a low logic level to enable the battery charger." Tied low, so charging cannot be disabled by firmware — deliberate. Has a ~285 kΩ internal pulldown but must not be left floating. |
| 5 | EN2 | `/CHG_EN2` → U1 pad 22 = GPIO18 | Input current limit select, Table 7-2. |
| 6 | EN1 | `/CHG_EN1` → U1 pad 9 = GPIO5 | Both EN pins have ~285 kΩ internal pulldowns, so the limit defaults to EN2=0/EN1=0 = USB100 = 100 mA until firmware drives them. |
| 7 | PGOOD | `/PGOOD_N` → U1 pad 25 = GPIO21, R37 100k to +3V3 | Open drain; pulls low when a valid input source is present. Spec asks a 1 kΩ–100 kΩ pull-up and 100k is the top of that range, chosen for standby current. |
| 8 | VSS | GND | "VSS pin must be connected to ground at all times" — the thermal pad alone does not satisfy this. |
| 9 | CHG | `/CHG_STAT` → U1 pad 34 = GPIO38, R38 100k to +3V3 | Open drain; low while charging, high impedance when charge completes **and** when the charger is disabled. Not an input-present signal on its own. |
| 10, 11 | OUT | `/SYS`, C30 10 µF | System supply output. Spec asks 4.7–47 µF. |
| 12 | ILIM | `/ILIM`, R35 1.6k to GND | Spec range 1100 Ω to 8 kΩ. I(IN-MAX) = KILIM/RILIM, KILIM typ 1610 AΩ (1500–1720), so 1610/1600 ≈ **1.01 A** typ and 0.94–1.08 A across the spread. Active only in the EN2=1/EN1=0 state. **Leaving ILIM open disables all charging**, so this resistor is not optional. |
| 13 | IN | `/USB_VBUS`, C1 100 nF + C2 10 µF | Input range 4.35–6.6 V, OVP at 6.6 V; survives 26 V without damage but suspends. Spec asks 1–10 µF bypass. |
| 14 | TMR | open | "Leave TMR unconnected to set the timers to the default values." Intentional — the default pre-charge and fast-charge safety timers are what is wanted. |
| 15 | SYSOFF | GND | BQ24075-specific pin. "Connect SYSOFF low for normal operation." It is internally pulled **up** to VBAT through ~5 MΩ, so grounding it is required rather than conventional: floating, the battery would be disconnected from OUT. |
| 16 | ISET | `/ISET`, R3 3.57k 1% to GND | Spec range 590 Ω to 8.9 kΩ. I(CHG) = KISET/RISET, KISET typ 890 AΩ (797–975), so 890/3570 ≈ **249 mA** typ and 223–273 mA across the spread — about 0.5C for a 500 mAh cell. **Charging is disabled if ISET is left unconnected.** |
| 17 | EP | GND | "There is an internal electrical connection between the exposed thermal pad and the VSS pin... Do not use the thermal pad as the primary ground input." Both EP and pin 8 go to GND. |

Table 7-2 is indexed **(EN2, EN1)** — the reverse of the order the pins are named in, which is an easy way to set the wrong limit:

| EN2 | EN1 | Maximum input current into IN |
|---|---|---|
| 0 | 0 | 100 mA, USB100 — the power-on default from the internal pulldowns |
| 0 | 1 | 500 mA, USB500 |
| 1 | 0 | Set by RILIM: 1.6 kΩ → about 1.0 A |
| 1 | 1 | Standby (USB suspend) |

**SYS rail voltage — check this on the bench.** V(OUT-REG) is 5.5 V and V(DPPM) is 4.3 V (Section 6). SYS feeds U6, and the TPS63031's recommended supply is 1.8–5.5 V with an absolute maximum of 7 V. Removing the old Schottky D2 raised SYS by that diode's forward drop, so a 5.0 V port now puts roughly 4.9–5.0 V on SYS instead of about 4.55 V. That is still inside the TPS63031's recommended range, and the behaviour above it improved: OUT regulates at 5.5 V rather than passing the input through, and the input OVPs at 6.6 V, where the diode would have handed a 7 V supply to the regulator at about 6.55 V. Steady-state headroom went down, the failure mode got safer. Measure SYS with a high-end-of-spec 5.25 V source before trusting it.

When the input is out of range, OUT is connected to VBAT (unless SYSOFF is high). That is what makes `SUPPLY_SENSE` on SYS_SW a battery reading while running unplugged — and why it is not one while charging.

## U9 — TI SN74LVC1G132 (was SN74LVC1G08)

[Manufacturer datasheet SLVS322](https://www.ti.com/lit/ds/symlink/sn74lvc1g132.pdf), Pin Functions table and Figure 4-1. Original PDF saved as `sources/SN74LVC1G132.pdf`.

DBV (SOT-23-5): 1 A, 2 B, 3 GND, 4 Y, 5 VCC — **identical to the SN74LVC1G08 it replaces**, so the footprint, the supply pins and the board land pattern are untouched.

Why it changed: R29/C26 form a 0.47 µs RC delay feeding this gate. The SN74LVC1G08 specifies a maximum input transition rate of 10 ns/V; that edge crosses the logic threshold region at roughly 250 ns/V, about 25× outside the datasheet. An LVC input driven slowly through its linear region can oscillate and draws shoot-through current. The 1G132 has Schmitt-trigger inputs and conditions **both** inputs, not just the RC branch.

It is a NAND, so Y now falls on a detection where the AND rose. U10's trigger moved to match:

| | before | after |
|---|---|---|
| U10 pin 1 (~A) | GND | U9 Y |
| U10 pin 2 (B) | U9 Y | +3V3 |
| triggers on | B rising, ~A low | ~A falling, B high |

The SN74LVC1G123 supports both edges, so this is a rewire rather than a redesign. Idle state is unchanged: with no emitter pulse, or a pulse with no tape return, Y sits high and ~A sees no falling edge.

## U6 — TI TPS63031DSKR

[Manufacturer datasheet SLVS696D](https://www.ti.com/lit/ds/symlink/tps63031.pdf), pin table/page 3 and fixed-output reference circuit. Original PDF saved.

1 VOUT; 2 L2; 3 PGND; 4 L1; 5 VIN; 6 EN; 7 PS/SYNC; 8 VINA; 9 GND; 10 FB; exposed pad represented by KiCad pad 11, tied to PGND. VIN/VINA/EN/PS-SYNC connect to switched SYS power (USB or battery). PS/SYNC high forces PWM. L1/L2 connect only through the 1.5 µH Murata DFE201612PD-1R5M=P2. FB connects directly to VOUT for fixed 3.3 V operation.

Input 10 µF + 100 nF are between SYS_SW and ground. Two 22 µF nominal output ceramics are between 3.3 V and ground, with at least 20 µF total effective capacitance required. All three ground/thermal pads join common ground. The net verifier explicitly checks both switching-node nets and every capacitor terminal.

## U7 — onsemi SRV05-4MR6T1G, USB ESD equivalent

[Manufacturer datasheet SRV05-4/D Rev 4, October 2024](https://www.onsemi.com/pdf/datasheet/srv05-4-d.pdf), page 1 pin diagram and USB application. Verified from manufacturer web PDF. This is the selected equivalent to the requested SRV05-4A.

1/3/4/6 are independent protected I/O channels; 2 is VN/ground; 5 is VP. Pins 1 and 3 protect D- and D+ respectively; unused channels 4 and 6 are NC. VP connects to USB VBUS with 100 nF bypass. The ordinary KiCad SRV05-4 symbol has the matching electrical pinout.

## Other pin and lead checks

- [AO3400A manufacturer datasheet, Rev 3.1](https://www.aosmd.com/sites/default/files/res/datasheets/AO3400A.pdf): SOT-23 top-view gate 1, source 2, drain 3. Its 2.5 V gate-drive specification supports 3.3 V drive. Local PDF saved.
- [GCT USB4105 drawing](https://gct.co/files/drawings/usb4105.pdf): USB 2.0 16-contact version, joined A6/B6 D+, joined A7/B7 D-, separate CC1/CC2 5.1 kΩ resistors, all VBUS/ground contacts and shield included. Local drawing saved.
- [LTR-4206E manufacturer lead drawing, distributor mirror](https://media.digikey.com/pdf/Data%20Sheets/Lite-On%20PDFs/LTR-4206E.pdf): lead 1 emitter, lead 2 collector; flat indicates collector. The matching normal `Q_Photo_NPN_EC` symbol is used. Current [Lite-On Rev D link](https://optoelectronics.liteon.com/upload/download/DS-50-92-0073/LTR-4206E%20Data%20Sheet%20%20Rev.D.PDF) was identified but direct retrieval was blocked; the available manufacturer-authored lead drawing is archived. Final formed-lead footprint remains a PCB-stage task.
- [LTE-4208 manufacturer lead drawing, distributor mirror](https://media.digikey.com/pdf/Data%20Sheets/Lite-On%20PDFs/LTE-4208.pdf): long lead anode, short/flat-side lead cathode. The schematic uses KiCad LED numbering 1 cathode / 2 anode; preserve this convention when creating the later footprint. Current [Lite-On Ver D link](https://optoelectronics.liteon.com/upload/download/DS-50-92-0015/LTE-4208%20Data%20Sheet%20Ver%20D.PDF) was identified but retrieval was blocked. Archived manufacturer drawing verifies lead polarity.

## ERC and unused-pin treatment

Only three electrically justified PWR_FLAG symbols are used: external USB VBUS, external/common ground, and switched SYS supply after the passive power switch. Neither converter output nor battery/charger node is given a redundant flag. NC markers identify unused module GPIOs, USB SBU contacts, spare ESD channels, the BQ24075 TMR pin, and the documented LM1815 unused/open-mode pins. The charger status pins are no longer among them: the BQ24075 drives PGOOD and CHG into GPIOs. As of Rev E the sheet also has no dangling wire stubs, so ERC is clean at 0 errors and 0 warnings. See the CSV/JSON audit for each case. ERC has no exclusions or disabled checks.


## Revision B — charging independent of SW1

> **Superseded in Rev E.** D2, Q3, R27 and R31 were removed when the MCP73831 gave
> way to the BQ24075, whose integrated DPPM power path does this internally and better:
> no diode drop, and the system runs with a defective or absent cell. Kept as the record
> of what the discrete topology was and why.


[Microchip AN1149, DS01149C, figures 5–7](https://ww1.microchip.com/downloads/en/AppNotes/01149c.pdf) supplies the directional-control topology. Charger VDD remains on USB_VBUS and VBAT remains on BAT. The USB Schottky feeds SYS; the P-channel MOSFET has drain on BAT, source on SYS and gate on USB_VBUS. SW1 connects SYS to SYS_SW. With valid USB, Q3 is OFF and USB supplies the load separately from the battery charging node. Without USB, R27 pulls Q3 gate down and the battery supplies SYS. Local application-note PDF saved.

- Q3 [AO3401A, manufacturer Rev 3.1 December 2023](https://www.aosmd.com/sites/default/files/res/datasheets/AO3401A.pdf): SOT-23 top view verified against standard library/footprint: 1 gate, 2 source, 3 drain. Maximum RDS(on) 85 milliohms at VGS=-2.5 V. The body diode points BAT to SYS; reversing source/drain would defeat USB isolation. Local PDF and pin drawing saved.
- D2 [Nexperia PMEG4010CEH, 12 October 2023 v3](https://assets.nexperia.com/documents/data-sheet/PMEG4010CEH.pdf): pin 1 cathode to SYS, pin 2 anode to USB_VBUS; SOD123F, 40 V, 1 A. Manufacturer web PDF verified; direct local download returned 403. Maximum pulsed VF at 25 C is 490 mV at 500 mA, 570 mV at 1 A. Provide thermal copper and verify operating temperature/current on the PCB.
- R27=1 kilohm gate pulldown uses about 5 mA/25 mW with 5 V USB. This is deliberately stronger than AN1149's typical 100 kilohms, limiting gate voltage caused by Schottky reverse leakage and speeding release at unplug. Temperature-dependent leakage and handover remain bench checks.
- C21=10 microfarads, 10 V X7R from SYS to common ground. C4/C5 remain on SYS_SW, never a switching node. USB must remain within the TPS63031 5.5 V input limit; use regulated 5 V only.
- R11/R12 now sense SYS_SW/2 on GPIO12, avoiding a direct USB-to-unpowered-GPIO divider path when OFF. Firmware must use SUPPLY_SENSE rather than treating GPIO12 as binary USB presence.

Expected states: USB absent/OFF = puck off; USB absent/ON = battery powers puck; USB present/OFF = battery charges, puck off; USB present/ON = USB powers puck and charger. Charge current remains approximately 249 mA, subject to charger thermal regulation and available USB current. Switch position does not interrupt the charger-to-battery path. All four cases require physical prototype confirmation, including USB handover, input droop and charge termination.

## J4 GPS header (2026-09-07)

Generic 1x05 2.54 mm header; no manufacturer pinout to verify. Assignment follows the common u-blox breakout order VCC, GND, TX, RX, PPS. GPIO1/GPIO2 are ordinary IOs on the ESP32-S3-MINI-1 (pads 5/6) routed to UART1 through the GPIO matrix; GPIO13 (pad 17) is the PPS input. GPIO3/45/46 strapping pins remain unloaded. Module must be 3.3 V logic and is supplied from the 3.3 V rail (about 30 mA active).

## Rev F — repo review responses (2026-09-13)

An external review of the repo raised the items below. Each was checked against the
manufacturer source rather than accepted or dismissed on its face.

**Confirmed and fixed.**

- **D1 peak current on USB.** The head runs from SYS_SW. With the BQ24075 regulating OUT
  to 5.5 V, R18 at 3.0 Ω gave roughly 1.1 A peak against D1's 1 A absolute maximum. The
  BOM note had only ever checked the 4.2 V battery case — it literally read "check peak
  at 4.2 V is under 1 A" — and the swap from the old Schottky path, which held SYS near
  4.55 V, is what pushed it over. **R18 is now 3.9 Ω**, chosen to keep the 500 mA design
  point at a full cell:

  | SYS_SW | peak into D1 (Vf ~2.2–2.45 V) |
  |---|---|
  | 3.3 V (low cell) | ~0.29 A |
  | 4.2 V (full cell) | ~0.49 A — the bench-set design point |
  | 5.0 V (USB typical) | ~0.66 A |
  | 5.5 V (BQ24075 OUT ceiling, low-Vf bin) | ~0.90 A, under the 1 A maximum |

- **Charger stuck at USB100.** EN1/EN2 have ~285 kΩ internal pulldowns and firmware never
  drove them, so the input limit sat at 100 mA — which covers system load *and* charge
  current together. `setupCharger()` now runs at boot and selects USB500 (EN2=0, EN1=1).
  USB500 is the ceiling on purpose: 500 mA is the most a non-negotiated port must supply,
  and this board has no USB-PD or BC1.2.

- **U6 switcher parts on the wrong face.** L1 and C4–C7 were on the back while U6 is on
  the front, putting vias in a 2.4 MHz switching loop. All five moved to the front; the
  BQ24075's C2/C3/C30 followed. The general "ICs front, passives back" rule does not
  survive contact with a switching converter.

- **U1 decoupling not at the 3V3 pad.** C8/C9 sat near x 125–127 while pad 3 is at
  x 118. They stay on the back — U1's body owns that part of the front — but C8 is now
  0.38 mm from the pad instead of ~9 mm.

- **Head board emitter loop.** R18 was at x 121 with Q1/C20 at x 103, so the ~0.5 A pulse
  loop spanned the board. The three now cluster in 6.9 × 3.3 mm. R21/C21 moved from 4 mm
  away from Q1 to 16 mm, and sit 3.6/3.9 mm from U8 pins 1 and 2. The residual ~8 mm run
  from the cluster up to D1 is set by D1's provisional 8 mm lens keepout and cannot be
  shortened until that keepout is confirmed against the real Ledil TINA holder.

**Confirmed, accepted as a trade-off.**

- **SW1 carries the whole system current.** Fetched the datasheet the review could not:
  Würth WS-SLTV 450301014042 is rated **300 mA switching, 24 V DC**, gold-plated copper
  contacts (`sources/WS-SLTV-450301014042.pdf`). Steady draw is about 180 mA — TPS63031
  input ~130 mA plus the head's ~50 mA average — so it is inside the rating in normal
  operation. ESP32-S3 BLE TX bursts push the regulator input to roughly 400 mA at a low
  cell, and switch-on inrush into C4/C5/C30 is briefly amps. The rating governs contact
  erosion over rated life and carry capability exceeds switching capability, so the
  consequence is reduced switch life rather than a failure. Accepted deliberately; the
  alternative was moving SW1 to the TPS63031 EN pin with a PFET for the head supply,
  which would have cost the physical power-cut behaviour the slide switch exists for.

- **Deep sleep is not low power.** Confirmed from the local datasheet: the LM1815's
  supply current is **3.6 mA typical, 6 mA maximum**, and it sits on the always-on 3V3
  rail along with the head's op-amp and comparator. A sleeping puck therefore draws
  milliamps, so a 500 mAh cell lasts days, not months. Recorded rather than fixed — a
  load switch on the LM1815 and head supply is the fix if flight logging ever depends on
  long sleeps.

**Not confirmed.**

- **U1 footprint.** The review suggested switching from `RF_Module:ESP32-S2-MINI-1` to an
  S3 footprint "since the S3 footprint exists in KiCad 10". It does not: KiCad 10.0.3
  ships `ESP32-S3-WROOM-1`, `-1U` and `-2`, but no `ESP32-S3-MINI-1`. The only MINI-1
  land patterns in `RF_Module.pretty` are the S2 ones. The ESP32-S3-MINI-1 and
  ESP32-S2-MINI-1 are the same 15.4 × 20.5 mm module with the same 65-pad pattern, so
  the S2 footprint is correct, not merely tolerable. Left as is; this note exists so the
  question does not get re-raised at the next review.

- **SUPPLY_SENSE on ADC2.** Agreed with the review's own conclusion: BLE alone does not
  block ADC2 oneshot reads in ESP-IDF 5.x, and Wi-Fi is never started. Already noted in
  `board.hpp`; no redesign.

**Outstanding — firmware, not blocking layout.**

- `readBlock` rejects any FIFO block whose level is not exactly 16, so interrupt latency
  above ~37 µs discards the block. Reading exactly 16 and leaving the remainder would be
  robust at the cost of a negligible one-sample timestamp shift.
- The emitter runs whenever TR-VERT is selected, idle or not, at roughly 90 mA average.
  Gating it on acquisition plus a settle window would help battery life.

## Rev E parts and changes (2026-09-13)

- **U5 MCP73831 → BQ24075RGT, and D2 / Q3 / R27 / R31 deleted.** The discrete
  arrangement charged the cell and OR-ed USB against the battery with a Schottky and a
  P-channel FET. The BQ24075 does the same job with an integrated DPPM power path, and
  brings things the discrete version could not: it powers the system and charges the
  battery independently, runs with a defective or absent pack, limits inrush to meet
  USB-IF, and applies VIN-DPM so a weak port sags rather than collapses. New support
  parts R3 3.57k (ISET, ~249 mA), R35 1.6k (ILIM, ~1.0 A), R36 10k (TS), R37/R38 100k
  (PGOOD / CHG pull-ups), C30 10 µF on OUT. Every pin is checked against SLUS810N in
  the U5 section above.
- **Four charger pins to GPIOs**: EN1 → GPIO5, EN2 → GPIO18, PGOOD → GPIO21,
  CHG → GPIO38. EN1/EN2 set the input current limit; PGOOD and CHG are open-drain
  status inputs, active low, with 100k pull-ups. Until firmware drives EN1/EN2 the
  internal 285 kΩ pulldowns hold USB100, so the puck charges at 100 mA out of the box.
- **R33/R34/C31 and `BAT_SENSE` removed.** They existed only so firmware could compare
  SYS_SW against BAT and infer USB presence. PGOOD reports a valid input source
  directly, from the device that actually arbitrates it, so the inference is
  unnecessary. Removing it also retires the 500 kΩ ADC source impedance and the ~2 µA
  standing drain on the cell. GPIO4 (U1 pad 8) is unused again and its no-connect is
  back in `review/unused-pins.json`.
- **Consequence worth recording**: `SUPPLY_SENSE` on GPIO12 is now the only supply
  measurement on the board, and GPIO12 is ADC2_CH1. ADC2 shares with the radio, which
  is why BAT_SENSE had been put on ADC1. Nothing is broken — SUPPLY_SENSE was always
  on ADC2 — but the design no longer has an ADC1 path to the supply, and firmware that
  needs a reading with the radio up has to deal with that.
- **Net class**: `/SYS` was added to the Power class (0.50 mm). It is the BQ24075's OUT
  rail and carries the whole system load, and it did not exist under the old topology;
  at the 0.20 mm default it would have been rated 0.74 A. The stale `Net-(D2-K)`
  pattern was dropped with D2.

## Rev D parts and changes (2026-09-13)

- **R33/R34 1M, C31 100 nF - BAT sense divider** *(removed in Rev E; the
  BQ24075's PGOOD pin reports input power directly)*: `BAT/2` onto U1 pad 8 = GPIO4, which
  is ADC1_CH3 on the ESP32-S3. ADC1 was chosen over ADC2 because ADC2 is shared with the
  radio; GPIO3 was avoided because it is a strapping pin. U1 pad 8's no-connect was
  removed and the pin dropped from `review/unused-pins.json`.
  SUPPLY_SENSE (100k/100k on SYS_SW) alone cannot separate USB from battery. SYS is fed
  from USB through D2 or from the cell through Q3. USB at the low end of spec (4.75 V)
  minus D2's forward drop (PMEG4010CEH, ~0.45 V at a few hundred mA) gives ~4.30 V,
  against a full cell at 4.20 V - inside 1 percent divider tolerance plus the
  ESP32-S3's ADC error. Comparing SYS_SW against BAT is a differential test and
  separates them: `SYS_SW > BAT + ~0.3 V` means USB present.
  1M/1M, not 100k/100k: this divider sits directly on the cell and drains it whenever
  SW1 is off. 1M/1M is ~2.1 uA (decades against 500 mAh); 100k/100k would be ~21 uA
  (under three years). The consequence is a 500k source impedance at the ADC - C31
  supplies the sampling charge, and firmware must use a long sample time and
  multisample or the reading will sit low.
- **SW4 (RESET) deleted**: SW1 feeds U6 (TPS63031) pins 5/6/7/8, i.e. VIN and EN, so the
  power slide removes power from the regulator and therefore the MCU. A dedicated EN
  button was redundant. `Net-(U1-EN)` keeps R4 (10k pull-up), C10 (1 uF) and TP13.
- **R5 deleted**: R5 and R9 were both 10k from `/BOOT` to +3V3 - two pull-ups in
  parallel, 5k effective. The generator built the BOOT net in two blocks and each added
  its own. R9 was kept because it sits beside SW3. BOOT is now U1.4, R9.2, SW3.2, TP14.1.
- **Optical chain moved** to `BalancerREF_OptHead`: D1, PD1, Q1, U4, U8, R18-R28, C20-C25.
  Their pin verifications above remain valid and are now checked by that project's
  `scripts/verify_head.py`. What crosses is J5, a 7-way cable.

## Rev C parts (2026-09-09)

- **U2 ST IIS3DWBTR**, DS12569 Rev 4 Table 1 (page 3): 1 SDO/SA0, 2 RES, 3 RES (connect to VDD_IO or GND; wired to GND), 4 INT1, 5 VDD_IO, 6 GND, 7 GND, 8 VDD, 9 INT2, 10 RES, 11 RES (connect to VDD_IO or leave unconnected; left open and soldered), 12 CS, 13 SPC/SCL, 14 SDI/SDO/SDA. Only SPI supports full-rate operation; I2C is single-axis only and not used. 100 nF on VDD and VDD_IO. KiCad footprint Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y (14 pads).
- **U10 TI SN74LVC1G123DCTR**, SCES586E Table 4-1: 1 A (falling-edge trigger, held low), 2 B (rising-edge trigger, from U9), 3 CLR (active low, tied to VCC), 4 GND, 5 Q, 6 Cext, 7 Rext/Cext, 8 VCC. Rext 100k from Rext/Cext to VCC, Cext 1 nF between Cext and Rext/Cext; nominal output about 100 us, retriggerable.
- **U9 TI SN74LVC1G08DBVR** SOT-23-5: 1 A, 2 B, 3 GND, 4 Y, 5 VCC (standard KiCad symbol). *Superseded in Rev F by the SN74LVC1G132 - same pinout, Schmitt inputs, NAND instead of AND. Do not order from this line.*
- **U8 TI TLV9062IDR** SOIC-8 standard dual op amp pinout (1 OUT1, 2 IN1-, 3 IN1+, 4 V-, 5 IN2+, 6 IN2-, 7 OUT2, 8 V+); KiCad Amplifier_Operational:TLV9062xD units A/B/C.
- **PD1 Vishay BPW34S**: KiCad Sensor_Optical:BPW34, pin 1 cathode (to +3V3), pin 2 anode (to the transimpedance input); footprint OptoDevice:Osram_BPW34S-SMD.
- **D1 Cree XPEBRD-L1** red XP-E2: KiCad Device:LED numbering 1 K / 2 A on LED_SMD:LED_Cree-XP; Vf about 2.2 V, 1 A absolute maximum; driven at about 500 mA peak, 10 percent duty.
- **D3 SMF5.0A**: bidirectional-symbol Diode:SMF5V0A, either orientation valid; footprint Diode_SMD:D_SMF.
- **Q4 AO3401A**: same pinout as Q3 (1 G, 2 S, 3 D); drain to J2 pin 1, source to BAT, gate to GND.
