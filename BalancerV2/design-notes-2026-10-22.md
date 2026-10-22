# HoboBalancer v2, design notes, 2026-10-22

Two units. The **main unit** mounts on the airframe, carries the tach and both
accelerometers, runs on a 3S pack, and streams 1/rev vectors over BLE. The **control
head** is an off-the-shelf 7 inch ESP32-S3 touch display on its own cell; it runs the
multi-regime solver and docks on the main unit to charge.

## Sensors (owned)

| Role | Part | Interface | Notes |
|---|---|---|---|
| Tach | Banner SM312LVMHSQD | 10-30 V supply, NPN + PNP outputs, 0.3 ms response, M12 4-pin QD | Retroreflective, tape on one blade. Mating cordset MQDC-406. Pin 1 supply, pin 3 common, outputs on 2 and 4: confirm NPN pin on the label. |
| Vert accel | DSS 1460-x from MicroVib II kit | IEPE (ICP), ~20 mV/g per DSS app note | Confirm IEPE with diode test centre pin to shell. 1460-3 datasheet not found; PCB 328M215 is the custom ICP part DSS names in the prop note. |
| Lat accel | same | same | |

Sensors stud-mount to the main unit base plate. The plate is the sensor mount, so it is
machined aluminum, hard-mounted, no rubber, resonance above tail-rotor 1/rev.

## Main unit block diagram

```
 3S pack 9-12.6 V ──fuse/RPP──┬── buck 5 V ──┬── dock pogo 5 V (switched by dock-detect)
                              │              └── buck/LDO 3.3 V ── ESP32-S3, ADS131M02
                              └── boost 24 V ─┬── Banner SM312 supply
                                              └── IEPE CC 4 mA ×2 ── sensors

 SM312 NPN ── 10k pull-up to 3.3 V, 1k series ── ESP32 MCPWM capture (tach)

 IEPE ch ── 10 uF AC couple ── OPA2320 gain x10, RC anti-alias 1 kHz ── ADS131M02 ch (x2, simultaneous)
 ADS131M02 ── SPI + DRDY ── ESP32-S3 ── BLE NUS ── control head
```

Charging the pack: 12.6 V CC/CV charger IC (BQ24610 class) from a barrel jack or USB-C
PD at 15 V, into a protected 3S pack with its own BMS. Balance lead brought out to a
JST-XH for a hobby charger as the fallback.

## Front end detail

- 24 V rail: boost (TPS55340 or LT8362 class), 100 mA budget.
- IEPE source: 4 mA constant current per channel, LT3092 or a 2-terminal CRD. The SST507
  (2.16 mA) from the Rev A order is in spec for short cables but at the low edge.
- Sensor bias sits at 8-12 V DC; AC-couple with 10 uF film, 1 M bias to a mid-rail.
- Gain x10: 20 mV/g becomes 200 mV/g. A 0.05 g 1/rev is 10 mV at the ADC; ADS131M02
  full scale is +/-1.2 V differential, so headroom to about 6 g peak.
- Anti-alias: single RC at ~1 kHz; the ADC's own sinc filter does the rest. Sample 4 kSPS.
- Flat phase at rotor frequencies matters more than bandwidth. Keep the AC-coupling corner
  below 0.5 Hz so phase error at 6.5 Hz (390 RPM) is under 5 deg and calibratable.

## Power budget, main unit

| Load | Rail | Current | Power |
|---|---|---|---|
| ESP32-S3 with BLE | 3.3 V | 100 mA | 0.33 W |
| ADS131M02 + op amps | 3.3 V | 10 mA | 0.03 W |
| Banner SM312 | 24 V | 25 mA | 0.60 W |
| IEPE 2 ch | 24 V | 8 mA | 0.19 W |
| Converter losses | | | 0.25 W |
| **Running total** | | | **~1.4 W, ~130 mA from 3S** |
| Dock charging head | 5 V | up to 1 A | 5 W, only when docked |

A 2200 mAh 3S pack gives roughly 15 h of measurement, or about 4 h if the head is
charging at full rate the whole time.

## Control head candidates

| Board | Panel | Battery | Notes |
|---|---|---|---|
| Elecrow CrowPanel Advance 7 | 7 in 800x480 IPS, GT911 touch | 1S charger onboard, RTC with coin cell | Preferred: IPS for outdoor angles, RTC for flight timestamps |
| Waveshare ESP32-S3-Touch-LCD-7B | 7 in 1024x600, 5-point touch | CS8501 1S charger onboard, 580 mA | Higher resolution, more I/O (CAN, RS485) |

Dock: three pogo pins, 5 V, GND, dock-detect. The head's own charger handles the cell.

## Firmware split

- Main unit: port the carrier firmware's capture, FIFO, sync demodulation and BLE NUS
  stream; replace the IIS3DWB driver with an ADS131M02 driver. Output per revolution:
  vert and lat vector, RPM, quality flags.
- Head: LVGL UI, regime-by-regime entry, polar chart, multi-regime least-squares solver
  with track constraint, flight log on flash or SD.

## Open items

1. Diode-test the 1460 sensors and read the label for sensitivity and connector type.
2. Confirm which SM312 QD pin is NPN.
3. Pick pack: protected 3S 18650 pack vs hobby LiPo with external BMS.
4. Enclosure: base plate stiffness and sensor boss layout before any PCB outline.
