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
| 2 | 0.789 | 25 | 320 | 340 | none (row 1 CHG columns are 0) |
| 3 | 0.933 | 37 | 1206 | 97 | 278.7 g at 180 |
| 4 | 0.682 | 271 | 739.2 | 75 | +753.2 g at 90 and -753.2 g at 180 (combined 1065.2 at 45) |
| 5 | 0.248 | 253 | 666.5 | 79 | 301.8 g at 180 |
| 6 | 0.197 | 183 | 394.3 | 61 | 102.8 g at 180 |
| 7 | 0.410 | 147 | 276.7 | 328 | -76.3 g at 90 |
| 8 | 0.213 | 185 | 184.8 | 332 | 50.9 g at 90 |

(Change column corrected 2026-11-14 from MicroBase's Balance History panel: its CHG1/LOC1,
CHG2/LOC2 columns on row N are the change entered AFTER run N, i.e. before run N+1; the +44/+48
field of record N+1 holds the same change as one combined vector, and that is what run N+1's
SENS/TACH were learned from, which reproduces every value above. After run 8 the panel shows
15.7 g at 90 and -36.1 g at 180 entered with no run 9. Negative entries are removals: the C32
sign is bit 7 of the exponent byte, which earlier decoding read as 2^130 and called garbled.)

Two things learned:
- CORRECTED 2026-11-14: the level field at +28 is C32, not float32, and read that way it IS
  the displayed level on every run of both files (the "range factor" was the float misread,
  the same bug as in the .SPC decoder). mag/SENS only checks the stored solution block, which
  is garbled in runs 3, 6 and 8 here; MicroBase shows those runs normally and so does mv2.js.
- SENS and TACH are re-learned after every entered change, as a single-step replacement:
  SENS = |W| / |V_after - V_before|, TACH from the response angle. Checked on runs 2 to 3:
  278.7 g at 180 moved the vector from 0.789 at 24.8 to 0.933 at 36.9, which gives
  SENS 1205.6 and TACH 97.4 against the MicroVib's 1206 and 97. There is no averaging
  across runs and no use of earlier runs, which is the snapshot behaviour to improve on.

## PLOT0093.SPC on screen (MicroBase, 2026-10-22)

Spectrum average, 200 points, Hann window, 4 averages, units IN/S PK, x-axis 75 to
15000 RPM (CPM), i.e. 1.25 Hz per line over 250 Hz; overall 0.5057. Peak table: main
rotor 353 CPM at 0.264, main rotor 2x 736 CPM at 0.094, 4x at 0.167, 8x at 0.115, tail
rotor 0.030. CORRECTED 2026-11-14: the 200 values are NOT IEEE floats but the MicroVib's
C32 format; read as floats they came out off by powers of two, and "bin 5 = 0.2647 matches
the 1x" was a coincidence of that misread. Decoded as C32 (decode_grp.py, verified bin by
bin against MicroBase's own unpacked spectrum, test_decode_spc.py) the bins are peak IN/S,
bin k at (k+1) x 1.25 Hz with no DC bin, and the 1x/2x/4x/8x peaks sit on bins 4, 9, 19, 40
(0.255, 0.094, 0.147, 0.115); the screen's 0.264 at 353 CPM and 0.167 for 4x are evidently
peak-interpolated between bins. RSS of bins 3.. is 0.498 against the screen overall 0.5057;
how the overall is formed is not pinned.

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

## Confirmed against DSS's own public material (2026-11-13)

Read from dssmicro.com; everything below was previously inferred from the two history files.

- **Learning formulas.** The DSS Balance Worksheet (download/Balwksht.pdf) prints
  `Ws = M/Vm` and `To = -(Vd+L)`: weight sensitivity is weight magnitude over vibration
  change magnitude, and tach offset is minus the sum of the vibration-change angle and the
  weight location. `mv2.js` `M.learn` computes exactly this. Its columns (RPM, VIB-IN/S,
  VIB-PHS, WHT-1/LOC-1, WHT-2/LOC-2, SENS, TACH) are the .HST record field order.
- **Units.** Vibration level is peak velocity in inches per second
  (faqs/faq_mv2_balance_readings.htm). Default prop factors: 80 g/IPS, tach offset 90 deg
  for the recommended 90 deg accelerometer-to-photo-tach installation
  (faqs/faq_mv2_balance_solutions.htm). The factors are a seed; learning replaces them after
  run 2, which is how the solver treats the profile values.
- **Phase definition.** DSS: "the rotation angle between the heavy spot of the rotor pushing
  the accelerometer in its positive direction, and the tach signal." That is an
  acceleration-peak reference. The carrier's `adjusted_velocity_phase_deg` is the positive
  velocity peak, 90 deg away; its `signed_acceleration_phase_deg` is the comparable quantity.
  Which of the two, and in which angular direction (DSS protractor: BLUE side for apparent
  CCW rotation, RED for CW, 0/360 on the adjustment location nearest the phase reference),
  must be fixed by a bench comparison before MicroVib-learned coefficients are used with
  carrier readings. Open item.
- **Rotor geometry.** Program Rotor mode: at most eight locations with angle and radius,
  units labels such as GRAMS/FLATS/POINTS/PLATES, every solution split between two valid
  locations, NEW SPLIT picks another pair (faqs/faq_mv2_rotor_geometry.htm). Standard Rotor
  mode: any number of hand-entered angles, radius 1.0, units WTS. The group-file record
  (name, channel, initial SENS, initial TACH, rotor mode, locations with units/name/angle/
  radius) matches decode_grp.py.
- **MicroBase Pro database** (faqs/faq_mbp_database_3rd_party.htm): dBase III/IV files in the
  data folder's `mbase` subfolder. `header.dbf` has one row per data item (DATE, TIME,
  AC_DESC1 aircraft, CP_DESC1 component, GROUP, TASK, ANLMODE, SAVEKEY). `histrecs.dbf` has
  one row per balance run (DATE, TIME, RPM, NEWPK, NEWPH, TRIAL, REMOVE, SPLIT, SENS, TACH,
  SAVEKEY). Spectra are log-packed one byte per bin in `specrecs.dbf` with MINVAL/MAXVAL/
  COUNT/FMAX from `saverecs.dbf`; waveforms linear-packed over 254. These are DSS's own
  decoded values and are the reference for checking mv2.js against, including the eight
  A1090021 runs whose decoded levels disagree with the screen. Not yet obtained.
- **Data identity.** MicroBase keys every item by aircraft ident/model/serial and component
  name/model/serial (help: Identifying MicroVib II Data). The solver keys by aircraft; a
  component field is still to be added.
- **Tach limits.** Minimum input speed about 150-180 RPM; HIGH TACH on double pulses
  (faqs/faq_accy_photo_tach.htm), the case the carrier now flags as ExtraTachPulses.
- **Field-check reference.** DSS Signal Simulator P/N 1117-2: 1920 RPM, 0.8 IN/S at 272.5 deg;
  accuracy 0.5 RPM, 5%, 0.8 deg (faqs product compatibility page). Carrier simulator preset
  `dss-simulator`; the bench comparison against a MicroVib II should be judged to the same
  tolerance. DSS accelerometers are 20 mV/g ICP; the magnetic pickup is a 900-1100 ohm coil.

## From DSS AN-MV2-A109 Rev 03 (19 Oct 2021), the A109 application note (read 2026-11-14)

- **Tasks and channels.** GND LT and HOV LT on CH:1A (lateral sensor, axis right); HOV VT,
  80KT VT, 140KT VT, MCP VT on CH:2A (vertical sensor, axis up); both sensors on one triaxial
  bracket on the beam between the seats. Tach from the magnetic pickup, cannon plug above the
  left pilot seat (photo-tach alternative: beam up and slightly forward, tape on the target
  blade grip when it is forward-right). T/R BAL on CH:4D: sensor on the T/R gearbox cover,
  axis up; photo-tach on the fin trailing edge, beam parallel to the output shaft, tape on a
  blade grip at the 2:00 position viewed from the left.
- **Angles.** Main rotor viewed from above: 360 TARGET forward-right, 90 A aft-right, 180 B
  aft-left, 270 C forward-left; A109E/SP has the magnetic pickup aft instead of forward. Tail
  rotor turns clockwise viewed from the left (protractor red side); wheel 360 at top, 90 left,
  180 bottom, 270 right. On both rotors the position numbers increase against the direction
  of rotation, the DSS protractor convention.
- **Limits.** Main rotor: 400 g maximum in a single bolt; only adjacent blades should carry
  balance weights; trim tab +/-8 deg; one pitch-link graduation about 0.12 in of track.
  Tail rotor: twelve-position balance wheel on the standard balance program; at most four
  bolts on the flange; 25 g per bolt including bolt and nut; 100 g per flange; head toward
  the hub. The solver's built-in A109 profile now carries all of these as placement rules;
  its group-file template listed six T/R positions, which was wrong.
- **Procedure.** Ground track to 0.5 in spread, then GND LT lateral; hover track, HOV VT for
  reference; HOV LT preliminary balance; 80KT, 140KT and MCP track and vertical, the first
  vertical correction by tab from the track picture entered into all three tasks (tab up on
  the TARGET blade = +1.0 at 360), later ones from the displayed solution, always split across
  90/180/270/360; final HOV LT; autorotation check; 140KT spectrum. Acceptance 0.2 in/s on
  every task. Minimum 5 averages (AVGS=5) on every balance reading.
- **Speeds.** Main rotor 385 NR at 100% (4P blade rate 1540 CPM, 25.67 Hz); tail rotor 2096
  RPM. These set the expected speed bands for the carrier profiles.
- **DVA.** Absorbers tuned to 1524 CPM pilot / 1530 CPM copilot (A109E/S/SP), 2 mm washer
  about 6 CPM; cabin 4P at 140 kt 100% NR should be 0.6 in/s or less. Spectrum feature only.

## MicroBase Pro database cross-check (histrecs.dbf, header.dbf; read 2026-11-14)

DSS's own decoded balance history, from the `mbase` folder (dBase files; layout per the DSS FAQ
"MicroBase Pro Database & 3rd Party Applications"; fields SAVEKEY, NUMREC, TRIAL, REMOVE, SPLIT,
RPM, NEWPK, NEWPH, OLDPK, OLDPH, WT1/LOC1/RAD1, WT2/LOC2/RAD2, SENS, TACH, CWT/CLC, DATE, TIME,
AVGTYPE, AVGS, BW, FS, PK). Analyzer: MV2 serial 2004, firmware 1.34.101.75.

- **A1090731.HST agrees exactly.** The five identified runs (SAVEKEY 1077-1081; 1078 is a
  duplicate of GND LT, and HOV LT at 13:09:16 was never identified) match mv2.js on level,
  phase, RPM, both solution weights and locations, SENS and TACH, to the four decimals stored:
  GND LT 0.0849 at 151.2785, 17.9214 g at 0 and 20.4147 g at 90; HOV VT 0.1693 at 262.5645;
  80KT VT 0.0926 at 181.4615; MCP VT 0.1443 at 190.8888. The averages byte (+21) also agrees
  (2, 1, 2, 2), so that field is confirmed; those runs were taken with fewer than the AVGS=5
  the application note calls for. `FS` is the auto-range full scale (1.638); `PK` (0.1964,
  0.5167...) is not the +28 level field and is not identified.
- **A1090021.HST** was read from MicroBase's Identify Data preview on 2026-11-14 (eight GND LT
  runs, 28 Aug 2025, flags LS, RPM 384): levels 0.682, 0.789, 0.933, 0.682, 0.248, 0.197,
  0.410, 0.213 with the phases and SENS/TACH of the table above. The level field decoded as
  C32 matches all eight; the previously "garbled" values were the float misread, and the
  "corrupt" solution blocks of runs 3, 6 and 8 were negative C32 entries (-753.2, -76.3, -36.1)
  read without the sign bit. Nothing in the file is corrupt.
- The DSS sample jobs in the same table (M-20J prop, AS350 driveshaft and main rotor, PT6
  props, 2016-2017 props) carry OLDPK/OLDPH, the move installed, and the SENS/TACH learned
  from it: a direct check of the learning formula on DSS's own numbers (see the solver test).
- **PLOT0093.SPC against saverecs row 1082 and specrecs** (same plot, identified 2026-09-03): the
  .SPC header F16 fields at 0x2a, 0x2e and 0x32 read 3.0, 250 and 1.25, matching DSS's FLOW,
  FMAX and DELTA (Hz per bin); COUNT 200, 4 averages, Hann window, IN/S, integrated from
  acceleration. DSS's stored MAXVAL 0.47308543 equals the file's bin 0 (1.89234173) divided by
  exactly 4, but bins 1-4 (1.23, 0.45, 0.38, 1.02) fit no single scaling and the stored MINVAL
  0.00039589 matches no bin closer than 0.2%. How MicroBase scales the first bins is therefore
  not established at first; specrecs.dbf settled it: the file values are C32, not float
  (see the corrected PLOT0093 section above and test_decode_spc.py).
- **trakrecs.dbf / waverecs.dbf / tags.dbf / system.dbf**: only DSS sample track and waveform
  data; 731H1.TRK and PLOT0101.TRK were downloaded but never identified (next SAVEKEY 1083).
  tags.dbf records the aircraft as N731HC, AW109SP, S/N 22474.
- **manager.dbf**: A1090021.HST was downloaded from the MV2 on 2026-09-04 but never identified,
  which is why header.dbf and histrecs.dbf have no rows for it. machrecs FACTOR is the
  machine-file linking factor (measured over nominal speed) per spectrum.
