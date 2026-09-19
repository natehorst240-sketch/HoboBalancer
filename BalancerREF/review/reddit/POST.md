# Draft follow-up for r/PCB "Design and Board Review" (thread 1wjh9hl)

Draft, 2026-09-19, written from the repo docs for the Rev G sheet. Paste-ready but
check it reads like you before posting. Images to attach are in this folder:
`HOBOVibe-RevG-full-sheet.png`, `01`..`05` block crops, `board-main-top.png`,
`board-main-bottom.png`, `board-head-top.png`.

## Replies to the first round

**Sand-Junior** (U9 float, D3 backwards, USB through the ESD IC): all three were
right and are fixed in Rev G. D3 was drawn cathode-to-GND, which would have clamped
VBUS through a forward diode; the SMF5.0A is unidirectional and the design notes had
it down as bidirectional, which is how it survived review. The SRV05-4 now has D-
in on pin 1 / out on pin 6 and D+ in on pin 3 / out on pin 4 (same net both ends, the
part has no internal I/O path, the trace makes the through-connection). U9's
OPT_COMP input comes from the optical head over a cable and floated whenever the head
was unplugged; it now has a 100k pull-down.

**z2amiller** (DPI, two-sided assembly): new images at 400/600 DPI. Your read of the
assembly was right: every IC, connector, switch and test point is on the front (32
parts) and the back is 0603 resistors and capacitors plus one SOT-23 (41 parts). The
exceptions are the switching-loop caps and inductor for the buck-boost and the
charger's input caps, which sit on the front next to their pins. The head board is
single-sided. Plan is PCBA or hotplate the front and hand-solder the back.

**Sam__** (explain each section): below.

## What it is

A rotor track-and-balance instrument for RC helicopters: a 50 x 50 mm "puck" that
straps to the frame and a separate 25 x 50 mm optical tach head. It reports RPM,
1/rev vibration magnitude and phase, over BLE or USB. It is meant for troubleshooting
and trend-watching, not as a replacement for calibrated balancing gear, and nothing
has been bench-validated yet. Second PCB, so please assume nothing is obvious to me.

Two measurement profiles: **MR-VERT** (main rotor) uses an external two-wire
variable-reluctance pickup for the 1/rev; **TR-VERT** (tail rotor) uses the optical
head against a strip of retroreflective tape.

## Section by section (main board, Rev G)

**MCU: ESP32-S3-MINI-1 (U1).** Chosen for BLE plus native USB, and because the
module carries its own antenna and flash. USB goes straight to the module's D+/D-
through 22 R series resistors (R6/R7). The 1x05 header J4 is an optional u-blox-class
GPS (3V3, GND, RX, TX, PPS) for an in-flight logging mode. Three switches: SW1 power
slide, SW2 acquire, SW3 boot. No reset button on purpose: SW1 feeds the regulator's
VIN and EN, so the power slide already power-cycles the MCU.

**USB and power input (J1, U7, D3, U5).** USB-C receptacle with 5.1k CC pull-downs
for a UFP. SRV05-4 ESD array on D+/D- (data lines routed through it, see above) and an
SMF5.0A 5 V TVS on VBUS. The charger is a BQ24075: it has an integrated power path,
so the system is powered from USB while the cell charges independently and the puck
runs with a flat or absent pack. R3 3.57k sets about 249 mA fast charge (0.5C for the
500 mAh cell), R35 1.6k sets the ~1.0 A resistor-programmed input limit. EN1/EN2 go
to GPIOs; the part powers up in USB100 (100 mA) because both pins have internal
pull-downs, and firmware raises it to USB500 at boot. PGOOD (open drain, 100k pull-up)
is the "USB present" signal to the MCU; an earlier revision tried to infer that from
two ADC dividers and it did not work reliably. TS gets a fixed 10k because the pack
has no thermistor; CE and SYSOFF are tied low; TMR left open for the default safety
timers.

**Battery (J2, Q4).** Single-cell 500 mAh LiPo with its own protection. Q4 AO3401A is
reverse-polarity protection in the battery lead (gate to GND: body diode conducts on
first contact, then the channel).

**3.3 V rail (U6).** TPS63031 buck-boost at 2.4 MHz, because a single Li-ion cell
crosses 3.3 V during discharge and the USB case is 5 V. Input 10 u + 100 n, output
2 x 22 u, 1.5 uH inductor. SW1 sits between the charger's SYS output and the
regulator. SUPPLY_SENSE is SYS_SW/2 into GPIO12 (100k/100k, 100 nF); it reads the
cell when unplugged and the input-derived rail when charging.

**Vibration sensor (U2).** ST IIS3DWB on 4-wire SPI. It is a wideband vibration
sensor rather than a motion accelerometer: fixed 26.7 kHz ODR, flat to 6.3 kHz, so
filter phase at rotor frequencies is negligible. INT1 data-ready goes to a GPIO. The
puck mounts vertically (UP / LEFT arrows on the silk) so the stiff in-plane axis is
vertical.

**Main rotor tach (U3).** LM1815 variable-reluctance sensor interface. The VR pickup
arrives on J3 through two 10k 1206 pulse-rated resistors in series into the LM1815's adaptive-threshold input; output
pulled up to 3V3 and read by a GPIO (MAG_TACH). It is the old automotive part but it
handles the huge amplitude range of a VR sensor without a comparator threshold to
tune. Downside noted below: it draws 3.6 mA typical on the always-on rail.

**Optical tach.** Modelled on an industrial retroreflective photoelectric sensor:
pulsed emitter plus synchronous detection, so ambient light and flickering lamps
cannot coincide with the emitter windows. The analog front end lives on the separate
head board (D1 and PD1 have no leads to form, so they need their own copper on the
bracket): D1 Cree XP-E2 red LED pulsed at 20 kHz / 5 us / about 500 mA by Q1 AO3400A
through R18 3.9 R from SYS_SW, with a 100 uF local reservoir; PD1 BPW34S reverse-
biased into a 10k transimpedance stage referenced to 1.65 V (U8A TLV9062), then a x12
inverting AC-coupled gain stage (U8B); U4 TS3021 comparator against a fixed ~1.03 V
threshold with 470k hysteresis. The cut between the boards is after the comparator so
the 7-way cable carries only DC rails and digital edges. Back on the main board U9
(SN74LVC1G132 Schmitt NAND) gates the comparator output against an RC-delayed copy of
the emitter pulse (R29 1k / C26 470 pF, about 0.5 us to match receiver latency) and
U10 (SN74LVC1G123, 100k / 1 nF, about 100 us retriggerable) stretches consecutive hits
into one OPT_TACH edge per tape pass. A red acrylic window and a baffle between D1 and
PD1 are part of the mechanical design.

**Board.** 50 x 50 mm, four layers: outer signal, In1 solid GND, In2 +3V3 plane. ICs,
connectors, switches and test points on the front; passives on the back under their
IC's pins, except the switching-loop parts noted above. Three fiducials per populated
face, deliberately asymmetric. M2.5 mounting holes at the corners; the ESP32
antenna overhangs the top edge so its keepout is off the board and away from the
aluminium bracket. Net classes: 0.2 mm default, 0.5 mm power, 0.8 mm for the
buck-boost switch node. USB pair is 0.2/0.15 but not an impedance solution; the S3's
native USB is Full Speed.

## Known open items (so nobody has to find them)

- Routing is not finished: SYS, SYS_SW, BAT and USB_VBUS were pulled off the 3V3
  plane layer and need re-routing on the outer layers, and the Rev G changes (U7
  pass-through, R39) are unrouted.
- Sleep is not low power: the LM1815 and the head's op-amp/comparator sit on the
  always-on 3V3 rail, so a sleeping puck draws milliamps.
- SW1 is rated 300 mA switching against about 180 mA steady draw with BLE bursts
  above that; accepted as reduced switch life for now.
- ERC shows 144 "endpoint off grid" warnings from two symbols sitting on a half-grid
  (U7, J1). Cosmetic, not yet cleaned up.

Full KiCad 10 project, ERC/DRC reports, pin audit and datasheet notes:
https://github.com/natehorst240-sketch/HoboBalancer
