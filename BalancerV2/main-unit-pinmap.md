# v2 main unit, pin map and parts, 2026-10-22

Carrier architecture (FeatherS3[D] on two headers) with the IIS3DWB replaced by the
EVAL-ADXL357Z on two 1x6 headers, the LM1815 MPU input kept, a Banner NPN tach input,
and 3S power. Enclosure and the MPU lead are the user's; both tach inputs land on
solder-wire pads like the carrier's J3.

## FeatherS3[D] GPIO assignments (ESP32-S3 GPIO numbers)

| Signal | GPIO | Notes |
|---|---|---|
| MAG_TACH, LM1815 pin 12 out | 1 | unchanged from carrier; RTC GPIO so it can wake the ESP32 |
| OPT_TACH, Banner NPN via 10k pull-up and 1k | 35 | unchanged |
| ACQUIRE button | 5 | unchanged |
| STATUS LED | 37 | unchanged |
| ACCEL SCK / MOSI / MISO / CS | 12 / 11 / 14 / 17 | same SPI pins as the carrier, now to ADXL357 |
| ACCEL DRDY | 18 | ADXL357 DRDY, MCPWM capture for timestamps |
| BOOST_12V_EN | 38 | firmware switches the Banner supply on only when the optical tach is in use |
| DOCK_DETECT | 33 | pogo pin, pulled up, grounded by the head's dock contact |
| DOCK_5V_EN | 39 | FeatherS3 LDO2 pin repurposed as a logic output to the dock 5 V switch |
| BAT_SENSE | 3 | 3S voltage through 100k / 27k to the ADC, 12.6 V reads 2.68 V |
| GPS UART | 10 / 7 / 6 | kept wired to a 1x5 header, optional |

## ADXL357 eval board headers

EVAL-ADXL357Z is 0.8 x 0.8 in with two 1x6 headers. P1: VDDIO, VDD, VSS, INT1, INT2,
DRDY. P2: V1P8ANA, V1P8DIG, MISO, CS, SCLK, MOSI. VDDIO and VDD both to 3.3 V; V1P8 pins
left open (internal LDO); CS, SCLK, MOSI, MISO, DRDY to the GPIOs above; INT1/INT2 open.
Pin order within each header must be taken from UG-1119 figures 5 and 6 before the
footprint is placed; this file does not assert it.

## Power

| Block | Part class | Notes |
|---|---|---|
| Input | Deans T on a lead to solder pads, 2 A polyfuse, P-FET reverse-polarity | 3S 9 to 12.6 V |
| 5 V buck | TPS54202 class, 2 A | feeds the FeatherS3 USB/5V pin and the dock |
| Dock 5 V switch | P-FET high-side, driven by DOCK_5V_EN | three pogo pins: 5 V, GND, DOCK_DETECT |
| 12 V boost | MT3608/SX1308 class, EN from BOOST_12V_EN | Banner supply only, 30 mA |
| 3.3 V | FeatherS3's own regulator | ADXL357 and LM1815 (2.5 mA) hang off it |
| Battery monitor | 100k / 27k divider to BAT_SENSE | firmware cutoff at 9.9 V, warning at 10.5 V |
| Charging | none on board | external balance charger on the pack's JST-XH lead |

## Retained from the carrier, unchanged

LM1815 section (U2, R5/R6 10k 1206, R7 150k, C2 1n, R8 1.6M, C3 330n, R9 5.6k), SW1,
LED1/R15, the FeatherS3 headers, and the GPS header. Removed: U3, U4, C4, C5, R10, R11,
R12, R13 (the optical head's sync gate and one-shot; the Banner sensor delivers a clean
logic edge and needs neither), U5 and its caps, J5.
