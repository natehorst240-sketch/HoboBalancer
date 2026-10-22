# HoboBalancer v2, design notes, 2026-10-22

Two units. The **main unit** mounts on the airframe, carries the tach and both
accelerometers, runs on a 3S pack, and streams 1/rev vectors over BLE. The **control
head** is an off-the-shelf 7 inch ESP32-S3 touch display on its own cell; it runs the
multi-regime solver and docks on the main unit to charge.

## Sensors (owned)

| Role | Part | Interface | Notes |
|---|---|---|---|
| Tach | Banner SM312LVMHSQD | 10-30 V supply, NPN + PNP outputs, 0.3 ms response, M12 4-pin QD | Retroreflective, tape on one blade. Mating cordset MQDC-406. Pin 1 supply, pin 3 common, outputs on 2 and 4: confirm NPN pin on the label. |
| Vert / lat accel | PCB 357 series (charge mode, ~50 pC/g class) and Dytran 3085C (charge mode, 10 pC/g, high temp) from the MicroVib II kit | Charge output, via DSS 1498 charge amp | 1498 output is 0.4 mV/pC (label value), voltage signal, MicroVib reads it with ICP power off. PCB 357 at ~20 mV/g after the 1498 is the rotor sensor; the 3085C at ~4 mV/g is for engines, too little signal at 390 RPM. |

Input mode is selectable: **IEPE** (4 mA source on, for 100 mV/g general-purpose sensors)
or **voltage** (source off, high-impedance AC-coupled, for the 1498 output). Sensitivity
is entered per channel as pC/g x 1498 cal factor, or mV/g directly.

Roadmap: v2 uses the 1498 in the chain (calibrated, no analog design). v2.1 option: an
on-board differential charge amp (JFET op amp, ~1 nF feedback, ~1 G feedback R for a
<0.5 Hz corner, guarded layout) to make the unit self-contained with the charge sensors.
Alternative at any time: two 100 mV/g IEPE sensors for the rotors.

Still needed from the 1498: power source (internal battery or connector pins), output
connector pinout and DC level, cal factor on its label, pC/g on each sensor label.

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

## Input range to match (MicroVib II spec, 20 mV/g sensor)

MicroVib: user-selectable or auto range from 16 V pk-pk down to 160 mV pk-pk full scale,
minimum measurable 0.05 mV. At 20 mV/g that is +/-400 g down to +/-4 g, floor 2.5 mg.

At rotor speed the same IPS is far less signal than the spec's 100 Hz figures:

| Rotor | f | 0.1 IPS | sensor out |
|---|---|---|---|
| main 390 RPM | 6.5 Hz | 0.011 g | 0.21 mV |
| tail 2400 RPM | 40 Hz | 0.065 g | 1.3 mV |

A 0.02 IPS main-rotor balance is 0.04 mV, below the single-sample floor. Resolution comes
from synchronous averaging over many revolutions, not from the ADC alone.

## Front end detail

- 24 V rail: low-noise boost (TPS55340 or LT8362 class) with a post-filter, 100 mA budget.
- IEPE source: 4 mA constant current per channel, LT3092 or a 2-terminal CRD. The SST507
  (2.16 mA) from the Rev A order is in spec for short cables but at the low edge. Source
  noise sets the floor; use a filtered reference, not a bare boost output.
- Sensor bias sits at 8-12 V DC; AC-couple with 10 uF film, 1 M bias to a mid-rail
  (corner 0.016 Hz, phase error at 6.5 Hz negligible).
- Unity buffer (OPA2320) into the ADS131M02 and use its internal PGA for ranging:
  gain 1 = +/-60 g, gain 128 = +/-0.47 g. This reproduces the MicroVib auto-range in
  firmware. ADC input noise at gain 128 / 4 kSPS is about 1 uV, i.e. ~50 ug.
- Anti-alias: single RC at ~1 kHz; the ADC's own sinc filter does the rest. Sample 4 kSPS.
- Firmware averages the 1/rev vector over a selectable number of revolutions (64 revs at
  390 RPM is 10 s and cuts noise by 8x). Report the averaging count with every reading.

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

1. Read pC/g off each accelerometer label and the cal factor off the 1498; find how the 1498 is powered and its output pinout.
2. Confirm which SM312 QD pin is NPN.
3. Pick pack: protected 3S 18650 pack vs hobby LiPo with external BMS.
4. Enclosure: base plate stiffness and sensor boss layout before any PCB outline.
