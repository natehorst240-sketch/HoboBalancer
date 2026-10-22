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
