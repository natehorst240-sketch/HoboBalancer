# HoboBalancer v2, design notes, 2026-10-22

Two units. The **main unit** mounts on the airframe, carries the tach and both
accelerometers, runs on a 3S pack, and streams 1/rev vectors over BLE. The **control
head** is an off-the-shelf 7 inch ESP32-S3 touch display on its own cell; it runs the
multi-regime solver and docks on the main unit to charge.

## Sensors

| Role | Part | Interface | Notes |
|---|---|---|---|
| Tach | Banner SM312LVMHSQD | 10-30 V, <25 mA, M12 4-pin QD: pin 1 brown +, pin 3 blue -, pin 2 white NPN (used), pin 4 black PNP (open) | Retroreflective, tape on one blade. Mating cordset MQDC-406. Datasheet 69943 Rev J p.12. MHS: 0.3 ms response, 0.3 ms repeatability (0.7 deg jitter at 385 RPM, averaged out), reduced sensitivity range. Outputs off for 100 ms after power-up: ignore edges for 200 ms. Shiny blades may need the polarizing filter or the SM312LP. |
| Vert + lat accel | ADI EVAL-ADXL357Z (ADXL357, 3-axis MEMS, 20-bit, +/-10/20/40 g, DC to ~1 kHz, SPI) | SPI + DRDY, 3.3 V | One board gives both axes. DC response: no low-frequency phase error at 390 RPM; only a fixed digital-filter group delay, calibrated out. ~80 ug/rtHz noise, ~4 ug/LSB at +/-10 g. About $50-60 at Digi-Key. |

Kit charge-mode sensors (PCB 357, Dytran 3085C) and the DSS 1498 charge amp stay with the
MicroVib for engine work. A voltage-input daughterboard for the 1498 output is a possible
v2.1 add-on, not on the first board.

The ADXL357 board bolts flat to the machined aluminum base plate through all its corner
holes, one axis along the aircraft lateral line, SPI lead under 150 mm. The plate is
hard-mounted to the airframe, no rubber, resonance above tail-rotor 1/rev.

## Magnetic pickup tach (decided 2026-10-22)

The aircraft's two-wire magnetic interrupter is the primary main-rotor tach; it pulses
when the TARGET blade is 45 deg right-forward of the cabin. v2 carries the carrier's
LM1815 input unchanged (two 10k 1206 series resistors, 150k/1n one-shot, 1.6M/330n
hold) on a two-pin lead to the cannon plug. The Banner photo-tach stays as the
alternate input and for the tail rotor. The MicroVib's TACH offset of 340 for this
setup is the reference the v2 phase calibration must reproduce.

## Main unit block diagram

```
 3S pack 9-12.6 V --fuse/RPP--+-- buck 5 V --+-- dock pogo 5 V (switched by dock-detect)
                              |              +-- 3.3 V LDO -- ESP32-S3, ADXL357
                              +-- boost 12 V -- Banner SM312 supply (~30 mA)

 MPU (2-wire VR) -- 2x 10k 1206 -- LM1815 -- ESP32 MCPWM capture (main rotor tach)
 SM312 NPN -- 10k pull-up to 3.3 V, 1k series -- ESP32 MCPWM capture (alternate / tail tach)
 ADXL357 -- SPI + DRDY (FIFO, 4 kHz ODR) -- ESP32-S3 -- BLE NUS -- control head
```

This is the carrier architecture with the IIS3DWB replaced by the ADXL357, a tach input
for the Banner sensor, and 3S power. No analog front end, no 24 V rail, no external ADC.

Charging the pack: 12.6 V CC/CV charger IC (BQ24610 class) from a barrel jack or USB-C
PD at 15 V, into a protected 3S pack with its own BMS. Balance lead brought out to a
JST-XH for a hobby charger as the fallback.

## Signal at rotor speed (for averaging counts)

| Rotor | f | 0.1 IPS | 0.02 IPS |
|---|---|---|---|
| main 385-395 RPM | 6.4-6.6 Hz | 0.011 g | 0.0021 g |
| tail 2096 RPM | 34.9 Hz | 0.057 g | 0.011 g |

ADXL357 noise at 100 Hz bandwidth is ~0.8 mg rms, so 0.02 IPS on the main rotor needs
synchronous averaging over tens of revolutions. Firmware averages the 1/rev vector over a
selectable number of revolutions (64 revs at 390 RPM is 10 s) and reports the count.
For reference, the MicroVib II with its 20 mV/g sensors ranges 16 V pk-pk down to
160 mV pk-pk full scale (+/-400 g to +/-4 g) with a 0.05 mV floor (2.5 mg).

## Power budget, main unit

| Load | Rail | Current | Power |
|---|---|---|---|
| ESP32-S3 with BLE | 3.3 V | 100 mA | 0.33 W |
| ADXL357 | 3.3 V | 1 mA | 0.00 W |
| Banner SM312 | 12 V | 25 mA | 0.30 W |
| Converter losses | | | 0.15 W |
| **Running total** | | | **~0.8 W, ~75 mA from 3S** |
| Dock charging head | 5 V | up to 1 A | 5 W, only when docked |

A 2200 mAh 3S pack gives roughly 25 h of measurement, or about 4 h if the head is
charging at full rate the whole time.

## Control head candidates

| Board | Panel | Battery | Notes |
|---|---|---|---|
| Elecrow CrowPanel Advance 7 | 7 in 800x480 IPS, GT911 touch | 1S charger onboard, RTC with coin cell | Preferred: IPS for outdoor angles, RTC for flight timestamps |
| Waveshare ESP32-S3-Touch-LCD-7B | 7 in 1024x600, 5-point touch | CS8501 1S charger onboard, 580 mA | Higher resolution, more I/O (CAN, RS485) |

Dock: three pogo pins, 5 V, GND, dock-detect. The head's own charger handles the cell.

## Firmware split

- Main unit: port the carrier firmware's capture, FIFO, sync demodulation and BLE NUS
  stream; replace the IIS3DWB driver with an ADXL357 driver (SPI, FIFO, DRDY, same shape). Output per revolution:
  vert and lat vector, RPM, quality flags.
- Head: LVGL UI, regime-by-regime entry, polar chart, multi-regime least-squares solver
  with track constraint, flight log on flash or SD.

## Decisions 2026-10-22

- Pack: Admiral 2200 mAh 3S 35C LiPo, T (Deans) connector, no BMS in the pack. Plan:
  charge externally with a hobby balance charger through the JST-XH lead; the main unit
  carries a fuse, reverse protection, a cell-voltage monitor on the ESP32 ADC, and a
  low-voltage cutoff at 9.9 V (3.3 V/cell). No onboard 3S charger. Confirm acceptable.
- Head: Waveshare ESP32-S3-Touch-LCD-7B (1024x600, CS8501 1S charger, 580 mA).
- A109 rotor speeds: main 395 RPM below 40 kt (6.58 Hz, 152 ms/rev) and 385 RPM in
  forward flight (6.42 Hz, 156 ms/rev); tail 2096 RPM (34.9 Hz, 28.6 ms/rev). Averaging:
  64 main revs is about 10 s, 64 tail revs is 1.8 s. 4P main is 25.7 to 26.3 Hz.
- MicroVib records on file: 731H1.TRK (HOV VT result), PLOT0093.SPC (DVA VT spectrum,
  200 lines). Field mapping pending the MicroVib's displayed values for the same records.

## Open items

1. Confirm external balance charging for the LiPo (vs an onboard 3S charger).
2. Enclosure: base plate stiffness, ADXL357 board position and axis, tach aim, before any PCB outline.

## Blade track, cost-effective route (proposal 2026-10-22)

Tach-triggered global-shutter camera. A Raspberry Pi Global Shutter Camera (IMX296,
external trigger pin) on a Pi Zero 2 W, with a 6-8 mm lens, mounted on the roof or nose
looking up along the tip path at the forward-right azimuth, the same place the MicroTrack
sits. The main unit fires the trigger from the MPU edge with a programmed delay of
k x period/4 so each frame catches blade k at the same azimuth. Tip height is the edge
position in the frame; lead-lag comes free from the horizontal position. Four heights per
revolution, averaged over N revolutions, give spread and per-blade height like the
MicroTrack. Pixel-to-inch scale from the set track distance and lens focal length, checked
once against the MicroTrack.

Numbers: A109 tip speed about 220 m/s; a 30 us exposure blurs the tip by about 7 mm, well
inside the 13 mm (0.5 in) track tolerance and symmetric about the edge. Daylight contrast
against sky is enough; dusk or night needs a floodlight and reflective tip tape.
Cost about $100-130 for Pi Zero 2 W, GS camera, lens and a housing. Alternative: a
two-beam V photodiode tracker (the MicroTrack principle) built from the OptHead's
SFH 2440 transimpedance front end; cheaper parts but analog calibration is harder and it
gives height only, no lead-lag. Not recommended for v2 over the camera.

## Acquisition simulation result (matlab/sim_acquisition.m, confirmed in MATLAB 2026-10-22)

0.1 IPS 1/rev with 0.6 IPS 4P on an ADXL357 model at 395 RPM: 16 revolutions give
0.0005 IPS and 0.3 deg scatter on the magnetic pickup, 0.0006 IPS and 0.5 deg on the
Banner photo-tach; both reach 0.0002 IPS and 0.2 deg at 64 revolutions. Resolution margin
over the 0.02 IPS requirement is about 40x. The sensor filter adds a constant 0.6 deg of
phase lag that calibrates out with the tach delay. Firmware default: average 32
revolutions on the main rotor and report the count with every reading; the magnetic
pickup is the primary main-rotor tach, the Banner the alternate and the tail-rotor tach.
