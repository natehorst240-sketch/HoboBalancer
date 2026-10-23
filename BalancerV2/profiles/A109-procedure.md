# A109 track and balance facts for the v2 solver (from DSS AN-MV2-A109 Rev 03 and A109.mdf)

## Rotor speeds
| Source | Main | Tail |
|---|---|---|
| AN-MV2-A109 | 385 NR (1540 CPM 4P / 4) | 2096 T/R RPM at 100% |
| A109.mdf (MicroBase machine file) | 6.4033 Hz = 384.2 RPM | 0.34722 x output shaft 100 Hz = 34.7 Hz = 2083 RPM |
| User, 2026-10-22 | 395 below 40 kt, 385 in forward flight | 2096 |
Resolved: NR is scheduled by airspeed. Ground and hover regimes run at 395 (6.58 Hz),
80KT/140KT/MCP at 385 (6.42 Hz). Tail 2096 RPM = 34.9 Hz. Output shaft 6000 RPM, tail
driveshaft 5876 RPM, 4P = 26.3 Hz at 395 and 25.7 Hz at 385. The firmware takes RPM from
the tach, so the schedule only matters for averaging-window and one-shot sizing.

## Main rotor regimes (group file matches)
| Task | Ch | Condition | Collect | Correct with |
|---|---|---|---|---|
| GND LT | 1A | 100% ground, flat pitch | track, lateral | track: pitch link; lateral: mass if > 0.2 IPS |
| HOV VT | 2A | hover IGE | track, vertical | track: pitch link to < 0.5 in spread; vertical saved only |
| HOV LT | 1A | hover IGE | lateral | mass if > 0.2 IPS |
| 80KT VT | 2A | 80 kt S&L | track, vertical | tab |
| 140KT VT | 2A | 140 kt S&L | track, vertical | tab |
| MCP VT | 2A | MCP S&L | track, vertical | tab |

Rules: first vertical correction is a tab bend judged from the track picture, entered into
all three VT tasks; after that the solution is in tab degrees split across 90/180/270/360.
Tab max +/- 8 deg. Mass max 400 g per bolt, adjacent blades only. Pitch link: one
graduation ~ 0.12 in track; shorten to bring a blade down. Minimum 5 averages. Done when
vertical and lateral are <= 0.2 IPS. Blades: TARGET = 360, then A 90, B 180, C 270.

## Tail rotor
Task T/R BAL, ch 4D, 100% ground, zero pitch. Twelve-position balance wheel, max 4 bolts,
25 g per bolt including hardware, 100 g per flange. Rotor turns clockwise viewed from the
left. Tape on a blade grip; tach on the aft edge of the vertical fin, beam parallel to the
T/R shaft, hitting the blade at the 2:00 position viewed from the left. Target <= 0.2 IPS.

## DVA (vibration absorber) tuning
Task DVA VT, spectrum peak-hold with a dead-blow hammer; natural frequency target 4P:
pilot side 1524 CPM (25.4 Hz), copilot side 1530 CPM (25.5 Hz). Cabin 4P at 140 kt should
be <= 0.6 IPS. PLOT0093.SPC is one of these plots: 200 lines, peak at bins 19-20, which at
1.25 Hz/bin is 23.75-25 Hz, consistent with the 4P target.

## Sensor and tach placement (main rotor)
Two 1460-3 accelerometers (20 mV/g) on the 1646 triax bracket on the structural beam
between the pilot and copilot seats: vertical up, lateral right. Tach: magnetic pickup on
the aircraft's own interrupter, or photo-tach pointing up and slightly forward at tape on
the blade grip with the target blade forward-right. Note for v2: the sensors are inside the
cabin and the tach is outside, so a single self-contained unit cannot carry both for the
main rotor unless it mounts on the roof.

## MicroBase balance-history row, GND LT, run 1 (screen capture 2026-10-22)

RPM 384.2 | LEVEL 0.085 IN/S | PHASE 151.3 | CHG1 17.9 g at LOC1 0 | CHG2 20.4 g at LOC2 90
| SENS 320.00 | TACH 340.0 | CH 1A | AVGS 2 | BW 10% | ORD 1 | WIND HANN | FS 1.6 | PK 0.20
| history file A1090731.HST, 09/01/2026 13:06:40, aircraft N731HC, AW109SP.

What this pins down:
- The two per-regime numbers in the .grp are SENS (adjustment per IPS: 320 g, 8 deg tab,
  16 g tail, 10 g DVA) and TACH (tach angular offset: 340 main, 90 shaft, 120 tail).
- Solution magnitude = SENS x LEVEL = 320 x 0.085 = 27.2 g; the split 17.9 g at 0 and
  20.4 g at 90 has magnitude 27.1 g. Angle from 0 toward 90 is 48.7 deg, which equals
  PHASE + TACH + 180 = 311.3 deg measured the other way round. Working convention for the
  solver: weight angle = phase + tach offset + 180, counted against rotation; split onto
  the two adjacent positions. Verify on a second record before trusting the sign.
- FS 1.6 and PK 0.20 are the display full scale and the 0.2 IPS target.

## MicroBase balance-history row, HOV VT, run 1 (screen capture 2026-10-22)

RPM 383.8 | LEVEL 0.169 IN/S | PHASE 262.6 | CHG1 0.5 at LOC1 270 | CHG2 0.2 at LOC2 0
| SENS 3.00 | TACH 340.0 | CH 2A | AVGS 1 | FS 1.6 | PK 0.52 | 09/01/2026 13:09:50.

Convention confirmed on both rows: solution angle on the rotor = -(PHASE + TACH + 180)
mod 360, magnitude = SENS x LEVEL, split onto the two adjacent positions.
- GND LT: -(151.3 + 340 + 180) mod 360 = 48.7; 17.9 g at 0 and 20.4 g at 90 give 48.7. Exact.
- HOV VT: -(262.6 + 340 + 180) mod 360 = 297.4; 0.5 at 270 and 0.2 at 0 give 291.8, within
  the one-decimal rounding of the two components.
HOV VT SENS is 3.00 even though the group file says NO ADJ for that task; the 0.5/0.2 are
in those units and are "save for reference only" per the app note.

731H1.TRK does not contain this row's numbers, so .TRK is a different record type,
probably blade track, not the vibration result.

## History file A1090731.HST, decoded (2026-09-01, N731HC)

| Task | Time | RPM | Level IPS | Phase | Solution |
|---|---|---|---|---|---|
| GND LT | 13:06:40 | 384.2 | 0.085 | 151.3 | 17.9 g at 0, 20.4 g at 90 |
| HOV LT | 13:09:16 | 384.1 | 0.028 | 75.9 | 7.5 g at 90, 5.1 g at 180 |
| HOV VT | 13:09:50 | 383.8 | 0.169 | 262.6 | 0.45 at 270, 0.23 at 0 (reference only) |
| 80KT VT | 13:13:26 | 384.2 | 0.093 | 181.5 | 0.70 deg tab at 0, 0.24 at 90 |
| MCP VT | 13:15:32 | 384.8 | 0.144 | 190.9 | 1.14 deg tab at 0, 0.18 at 90 |

All five satisfy magnitude / SENS = level and the angle convention above. This is the
solver's first regression set. A1090021.HST (2025-08-27, eight GND LT runs) decodes the
same way but carries non-zero bytes in the 16-byte block before SENS, presumably the
"enter changes" adjustments, which are not decoded yet; its levels (5 to 7 IPS) look like
a wrong sensitivity setting that day.

## Decisions 2026-10-22 (continued)
- Main unit mounts in the cabin directly under the magnetic pickup connector, above the
  copilot seat. The tach runs on a lead from there. The ADXL357 axes are set for that
  orientation at build time and confirmed with a 1 g check.
- LiPo charging is external through the balance lead; no onboard 3S charger.

## A1090021.HST decoded against the MicroVib screen (8 GND LT runs, 28 Aug 2025)

| Run | VIB IPS | PHS | SENS | TACH | entered change before this run |
|---|---|---|---|---|---|
| 1 | 0.682 | 354 | 320 | 340 | none |
| 2 | 0.789 | 25 | 320 | 340 | (block holds prev 0.682 at 354, change 7.9 at 0) |
| 3 | 0.933 | 37 | 1206 | 97 | 278.7 g at 180 |
| 4 | 0.682 | 271 | 739 | 75 | 301.8 g at 180 |
| 5 | 0.248 | 253 | 666 | 79 | 102.8 g at 180 |
| 6 | 0.197 | 183 | 394 | 61 | ... |
| 7 | 0.410 | 147 | 277 | 328 | 50.9 g at 90 |
| 8 | 0.213 | 185 | 185 | 332 | 15.7 g at 90 |

Two things learned:
- The stored level field is the displayed level times a range factor (x8 on this file,
  x1/x2/x4 on A1090731); mag/SENS always gives the displayed value, so use that.
- SENS and TACH are re-learned after every entered change, as a single-step replacement:
  SENS = |W| / |V_after - V_before|, TACH from the response angle. Checked on runs 2 to 3:
  278.7 g at 180 moved the vector from 0.789 at 24.8 to 0.933 at 36.9, which gives
  SENS 1205.6 and TACH 97.4 against the MicroVib's 1206 and 97. There is no averaging
  across runs and no use of earlier runs, which is the snapshot behaviour to improve on.

## PLOT0093.SPC on screen (MicroBase, 2026-10-22)

Spectrum average, 200 points, Hann window, 4 averages, units IN/S PK, x-axis 75 to
15000 RPM (CPM), i.e. 1.25 Hz per line over 250 Hz; overall 0.5057. Peak table: main
rotor 353 CPM at 0.264, main rotor 2x 736 CPM at 0.094, 4x at 0.167, 8x at 0.115, tail
rotor 0.030. The 200 IEEE floats in the file are the line amplitudes; bin 5 = 0.2647 and
bin 9 = 0.0943 match the listed 1x and 2x magnitudes, so the file stores displayed IN/S
PK directly. Exact bin-to-CPM alignment (k x 75 vs (k+1) x 75) still to be pinned.

## MicroBase settings relevant to the solver (mbsys.ini, read 2026-10-22, not stored: it holds a login)

- History: UseLearnLimit=YES, LearnLimit=0.10 IPS. MicroBase only re-learns the coefficient
  when the vibration change from a move exceeds 0.1 IPS. PredictMove=NO.
- AlarmVelEng=0.20 IPS, the acceptance level. PolarAutoFS=YES, PolarMinFS=1.0.
- Decision 2026-10-22: no track measurement in v2 at all. The solver treats the first tab
  move as a user-entered decision and otherwise works from vibration only.

## Tail rotor second adjustment (user, 2026-10-22)

Blade-bolt washers, 0.25 IPS per gram (four times the wheel's leverage because of the
larger radius), same direction convention as the wheel. Stations on the wheel scale:
TARGET blade (tape, 0 deg) bolt head 350, nut 10; blade 2 bolt head 170, nut 190
(estimated). Each station takes nothing or 5 to 16 g. The MicroVib's T/R BAL task only
knows the wheel; the solver searches the station combinations for least added mass with
the wheel inside 25 g per position. Direction confirmed by the user. Still open: whether
washers already on the bolts may be removed.
