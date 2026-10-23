# v2 main unit, pin map and parts, 2026-10-22

OMGS3 module soldered to pads, one 1S LiPo on the module's own charger and fuel gauge,
USB-C for charging and flashing, the EVAL-ADXL357Z on two 2x3 sockets, the LM1815 MPU
input kept, a Banner NPN tach input fed by a 12 V boost from the cell (decided
2026-10-22, replacing the 3S pack, the 5 V buck and the dock charger). Enclosure and the MPU lead are the user's; both tach inputs land on
solder-wire pads like the carrier's J3.

## OMGS3 GPIO assignments (ESP32-S3 GPIO numbers)

| Signal | GPIO | OMGS3 pad | Notes |
|---|---|---|---|
| BOOST_12V_EN | 3 | 5 | 100k pull-down on the MT3608 EN; firmware switches the Banner supply on only when the optical tach is in use. IO3 is a strapping pin (JTAG source) that only matters if that eFuse is burned |
| ACCEL SCK / MISO / MOSI / CS | 4 / 5 / 6 / 7 | 6 / 7 / 8 / 25 | the OMGS3 card's default SPI pins (CLK, MI, MO) plus IO7 as chip select |
| ACCEL DRDY | 10 | 22 | ADXL357 DRDY, MCPWM capture for timestamps |
| MAG_TACH, LM1815 pin 12 out | 11 | 21 | RTC GPIO |
| OPT_TACH, Banner NPN via 10k pull-up and 1k | 12 | 20 | |
| ACQUIRE button | 13 | 19 | 10k pull-up, 100 nF |
| STATUS LED | 14 | 18 | moved off IO8 on 2026-10-23 so the fuel-gauge I2C stays clean |
| GPS UART TX / RX | 43 / 44 | 1 / 2 | UART0, also the boot console; 1x04 header 3V3 / GND / RX / TX, optional |
| USB D- / D+ | | 14 / 15 | J9 USB-C, both pad pairs (A6/B6, A7/B7); CC1/CC2 5.1k to ground. Native USB flashing and USB Serial JTAG |
| IO0, RESET | | 13 / 11 | J5 1x03 header GND / IO0 / RST for manual bootloader entry; normally not needed |
| 5V in | | 12 | USB VBUS through D1 (SS14), as on Unexpected Maker's carrier; the module's charger and 700 mA 3.3 V LDO follow |
| BAT | | 17 | the 1S cell on J1 (JST-PH): charged by the module, read by its MAX17048 over IO8/IO9; also the boost input |
| 3V3 out | | 16 | feeds the ADXL357, LM1815 and the pull-ups |
| GND | | 10, EXP | |
| EN, IO8, IO9 | | 9, 24, 23 | open. EN defaults on; IO8/IO9 are the fuel-gauge SDA/SCL, keep them free |
| spare | 1, 2 | 3, 4 | free on the pads |

OMGS3 facts used here come from Unexpected Maker's pinout card and the P1 schematic
(github.com/UnexpectedMaker/esp32s3, read 2026-10-22): 17 GPIO on 25 pads plus the
exposed ground pad, 1.27 mm pitch, 25 x 10 mm, ESP32-S3-PICO-1-N8R2, IO33 VBUS sense,
IO34/IO35 RGB LED, IO8/IO9 MAX17048 I2C. The module is soldered flat to the board;
keep copper and the ground pour away from the antenna end (the last 8 mm).

## ADXL357 eval board headers (UG-1119 Rev A, figures 5 and 6, read 2026-10-22)

EVAL-ADXL357Z is 0.8 x 0.8 in with four corner mounting holes and two 2x3 (0.1 in)
header positions, P1 and P2, shipped unpopulated ("do not insert"): the user solders
pin headers into the vias. Both are 2x3, not 1x6.

| P1 pin | Signal | Main unit | P2 pin | Signal | Main unit |
|---|---|---|---|---|---|
| 1 | VDD (VSUPPLY) | 3.3 V | 1 | V1P8ANA | open |
| 2 | INT1 | open | 2 | CS/SCL | GPIO 17 |
| 3 | VDDIO | 3.3 V | 3 | V1P8DIG | open |
| 4 | INT2 | open | 4 | SCLK/VSSIO | GPIO 12 |
| 5 | VSS/VSSIO | GND | 5 | MISO/ASEL | GPIO 14 |
| 6 | DRDY | GPIO 18 | 6 | MOSI/SDA | GPIO 11 |

Odd pins are the left column, even the right, pin 1 at top-left in the figures. The
board's STBY 3-position jumper must be shunted to the side that keeps the part active;
confirm the STBY polarity in the ADXL357 datasheet pin table before first power. The
eval board has no reverse-polarity protection.

Mounting plan: the eval board bolts to the aluminum base plate through its four holes
with pin headers soldered pointing up; the main PCB stacks above it on standoffs with two
2x3 female sockets, so the sensor sits on the plate, not on the PCB, and there is no cable.

## Assembly plan (decided 2026-10-22)

Hand assembled, fewest distinct passive values, through-hole where reasonable.
- Through-hole: tach solder pads, JST-PH, SW1, ADXL357 sockets, PROG and GPS headers,
  the boost inductor.
- SMD, hand-friendly: ICs in SOIC or SOT-23 only; all passives 1206.
- ICs: LM1815 SOIC-14, MT3608 boost SOT-23-6.
- Resistors (five values): 10k, 100k, 1k, 1.6M, 5.1k (boost feedback and USB CC). LM1815 one-shot becomes 100k with the 1 nF kept (67 us pulse); the 5.6k pull-up
  becomes 10k.
- Capacitors (four values): 100 nF decoupling everywhere, 1 nF C0G one-shot, 330 nF
  LM1815 hold, 10 uF 25 V on the cell, VBUS and the boost output.

## Power

| Block | Part class | Notes |
|---|---|---|
| Cell | 1S LiPo, JST-PH, on the OMGS3 BAT pad | module charger (LP4055A, rate set on the module), MAX17048 fuel gauge over I2C |
| USB-C | 16-pin receptacle, VBUS through SS14 to the 5V pad, 5.1k on CC1/CC2 | charging, flashing, USB Serial JTAG; no TVS fitted |
| 3.3 V | OMGS3's own 700 mA LDO | ESP32, ADXL357, LM1815 (2.5 mA), pull-ups |
| 12 V boost | MT3608 from the cell, EN from BOOST_12V_EN | Banner supply only, ~25 mA at 12 V, ~100 mA from the cell |
| Battery monitor | the module's fuel gauge | no divider on the board |

Run time from a 2000 mAh cell: about 8 h with the Banner on, roughly double on the
magnetic pickup alone with the boost off. Charging the control head from a dock is no
longer on this board; the head charges on its own USB port.

## Reference designators in BalancerMain (generated 2026-10-22)

Generated by `BalancerMain/scripts/build_main.py` (schematic) and `build_pcb_main.py`
(placed, unrouted board); `verify_main.py` rebuilds the netlist from the schematic file
and checks every expected connection (39 nets). Rerun the three in that order after any
edit to the generators; hand edits in KiCad are fine once the generators are retired.

| Block | Parts |
|---|---|
| Cell | J1 JST-PH 2-pin to the OMGS3 BAT pad, C1 10u |
| USB-C | J9 16-pin receptacle (Unexpected Maker's footprint), R1/R2 5.1k CC pull-downs, D1 SS14 VBUS to the 5V pad, C2 10u |
| OMGS3 | U1 on pads, 3V3 pad is the 3.3 V source, J5 1x03 GND/IO0/RST |
| 12 V boost | U3 MT3608, R6 100k EN pull-down, L2 22uH, D2 SS14, C7 10u, R7 100k / R8 5.1k feedback (12.3 V) |
| MPU input | J3 pads, R9/R10 10k 1206 series, U4 LM1815, R11 100k / C8 1n one-shot, R12 1.6M / C9 330n hold, R13 10k pull-up, C10 100n |
| Banner input | J2 pads (brown +12V, blue GND, white NPN), R14 10k pull-up to 3V3, R15 1k series |
| ADXL357 | J6 (P1) and J7 (P2) 2x3 sockets |
| UI | SW1 6 mm tact, R19 10k, C11 100n; LED1 0603 green, R20 1k |
| GPS | J4 1x04 |
| Mechanical | H1-H4 M3 holes, 70 x 64 mm outline |

Passive values on the board: resistors 10k, 100k, 1k, 1.6M, 5.1k; capacitors 100n,
1n C0G, 330n, 10u 25V. Everything SMD is 1206 except LED1 (0603), the SOT-23-6 boost,
two SMA diodes, the SOIC-14, the USB-C receptacle and the OMGS3.

Before ordering: open the project in KiCad, run ERC and DRC, check the J6/J7 socket
spacing (15.24 mm centre to centre, pin 1 top-left on both) against the real
EVAL-ADXL357Z, keep the antenna end of the OMGS3 clear of copper, and route the board. The
converter loops (U2-L1-C5, U3-L2-D2-C7) want short, wide traces and a ground pour.
