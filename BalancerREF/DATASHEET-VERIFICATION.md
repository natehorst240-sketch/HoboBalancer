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

## U5 — Microchip MCP73831T-2ACI/OT

[Manufacturer datasheet DS20001984H](https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/MCP73831-Family-Data-Sheet-DS20001984H.pdf), SOT-23 table/page 11 and charging/application sections. Original PDF saved.

1 STAT, 2 VSS, 3 VBAT, 4 VDD, 5 PROG. 4.02 kΩ sets about 249 mA nominal. 10 µF input and output ceramic capacitors must retain at least the recommended 4.7 µF effective capacitance. The -2 option charges a 4.2 V cell. STAT is intentionally unused: MCP73831's tri-state output is not assumed to be a 3.3 V open-drain signal. Device thermal regulation can reduce the actual charging current.

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

Only three electrically justified PWR_FLAG symbols are used: external USB VBUS, external/common ground, and switched SYS supply after the passive power switch. Neither converter output nor battery/charger node is given a redundant flag. NC markers identify unused module GPIOs, USB SBU contacts, spare ESD channels, LIS2DW12 NC/INT2, charger STAT, and the documented LM1815 unused/open-mode pins. See the CSV/JSON audit for each case. ERC has no exclusions or disabled checks.


## Revision B � charging independent of SW1

[Microchip AN1149, DS01149C, figures 5�7](https://ww1.microchip.com/downloads/en/AppNotes/01149c.pdf) supplies the directional-control topology. Charger VDD remains on USB_VBUS and VBAT remains on BAT. The USB Schottky feeds SYS; the P-channel MOSFET has drain on BAT, source on SYS and gate on USB_VBUS. SW1 connects SYS to SYS_SW. With valid USB, Q3 is OFF and USB supplies the load separately from the battery charging node. Without USB, R27 pulls Q3 gate down and the battery supplies SYS. Local application-note PDF saved.

- Q3 [AO3401A, manufacturer Rev 3.1 December 2023](https://www.aosmd.com/sites/default/files/res/datasheets/AO3401A.pdf): SOT-23 top view verified against standard library/footprint: 1 gate, 2 source, 3 drain. Maximum RDS(on) 85 milliohms at VGS=-2.5 V. The body diode points BAT to SYS; reversing source/drain would defeat USB isolation. Local PDF and pin drawing saved.
- D2 [Nexperia PMEG4010CEH, 12 October 2023 v3](https://assets.nexperia.com/documents/data-sheet/PMEG4010CEH.pdf): pin 1 cathode to SYS, pin 2 anode to USB_VBUS; SOD123F, 40 V, 1 A. Manufacturer web PDF verified; direct local download returned 403. Maximum pulsed VF at 25 C is 490 mV at 500 mA, 570 mV at 1 A. Provide thermal copper and verify operating temperature/current on the PCB.
- R27=1 kilohm gate pulldown uses about 5 mA/25 mW with 5 V USB. This is deliberately stronger than AN1149's typical 100 kilohms, limiting gate voltage caused by Schottky reverse leakage and speeding release at unplug. Temperature-dependent leakage and handover remain bench checks.
- C21=10 microfarads, 10 V X7R from SYS to common ground. C4/C5 remain on SYS_SW, never a switching node. USB must remain within the TPS63031 5.5 V input limit; use regulated 5 V only.
- R11/R12 now sense SYS_SW/2 on GPIO12, avoiding a direct USB-to-unpowered-GPIO divider path when OFF. Firmware must use SUPPLY_SENSE rather than treating GPIO12 as binary USB presence.

Expected states: USB absent/OFF = puck off; USB absent/ON = battery powers puck; USB present/OFF = battery charges, puck off; USB present/ON = USB powers puck and charger. Charge current remains approximately 249 mA, subject to charger thermal regulation and available USB current. Switch position does not interrupt the charger-to-battery path. All four cases require physical prototype confirmation, including USB handover, input droop and charge termination.

## J4 GPS header (2026-09-07)

Generic 1x05 2.54 mm header; no manufacturer pinout to verify. Assignment follows the common u-blox breakout order VCC, GND, TX, RX, PPS. GPIO1/GPIO2 are ordinary IOs on the ESP32-S3-MINI-1 (pads 5/6) routed to UART1 through the GPIO matrix; GPIO13 (pad 17) is the PPS input. GPIO3/45/46 strapping pins remain unloaded. Module must be 3.3 V logic and is supplied from the 3.3 V rail (about 30 mA active).

## Rev C parts (2026-09-09)

- **U2 ST IIS3DWBTR**, DS12569 Rev 4 Table 1 (page 3): 1 SDO/SA0, 2 RES, 3 RES (connect to VDD_IO or GND; wired to GND), 4 INT1, 5 VDD_IO, 6 GND, 7 GND, 8 VDD, 9 INT2, 10 RES, 11 RES (connect to VDD_IO or leave unconnected; left open and soldered), 12 CS, 13 SPC/SCL, 14 SDI/SDO/SDA. Only SPI supports full-rate operation; I2C is single-axis only and not used. 100 nF on VDD and VDD_IO. KiCad footprint Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y (14 pads).
- **U10 TI SN74LVC1G123DCTR**, SCES586E Table 4-1: 1 A (falling-edge trigger, held low), 2 B (rising-edge trigger, from U9), 3 CLR (active low, tied to VCC), 4 GND, 5 Q, 6 Cext, 7 Rext/Cext, 8 VCC. Rext 100k from Rext/Cext to VCC, Cext 1 nF between Cext and Rext/Cext; nominal output about 100 us, retriggerable.
- **U9 TI SN74LVC1G08DBVR** SOT-23-5: 1 A, 2 B, 3 GND, 4 Y, 5 VCC (standard KiCad symbol).
- **U8 TI TLV9062IDR** SOIC-8 standard dual op amp pinout (1 OUT1, 2 IN1-, 3 IN1+, 4 V-, 5 IN2+, 6 IN2-, 7 OUT2, 8 V+); KiCad Amplifier_Operational:TLV9062xD units A/B/C.
- **PD1 Vishay BPW34S**: KiCad Sensor_Optical:BPW34, pin 1 cathode (to +3V3), pin 2 anode (to the transimpedance input); footprint OptoDevice:Osram_BPW34S-SMD.
- **D1 Cree XPEBRD-L1** red XP-E2: KiCad Device:LED numbering 1 K / 2 A on LED_SMD:LED_Cree-XP; Vf about 2.2 V, 1 A absolute maximum; driven at about 500 mA peak, 10 percent duty.
- **D3 SMF5.0A**: bidirectional-symbol Diode:SMF5V0A, either orientation valid; footprint Diode_SMD:D_SMF.
- **Q4 AO3401A**: same pinout as Q3 (1 G, 2 S, 3 D); drain to J2 pin 1, source to BAT, gate to GND.
