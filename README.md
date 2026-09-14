# HoboBalancer

Hobby helicopter rotor-balancing instrumentation. KiCad 10 projects plus ESP32-S3
firmware.

> **Reference and troubleshooting only.** These boards report approximate RPM, 1/rev
> vibration magnitude, phase, stability and trends. Maintenance balancing remains with
> calibrated MicroVib / DynaVibe equipment. Neither the firmware nor the physical
> measurement accuracy has been validated on a bench, let alone on an aircraft. Nothing
> here is airworthiness-approved.

Open the projects in **KiCad 10.0.3 or later**. They use the KiCad 10 file format and
KiCad 9 will not open them.

## Projects

| Directory | Board | Revision | State |
|---|---|---|---|
| `.` (root) | `Balancer` — STM32 balancer | Rev A | Schematic only; `Balancer.kicad_pcb` is an empty stub |
| `BalancerREF/` | **HOBOVibe** — ESP32-S3 reference puck | **Rev F** | 50 × 50 mm, 4 layer, placed, unrouted |
| `BalancerREF_OptHead/` | Optical tach head | **Rev B** | 25 × 50 mm, 2 layer, placed, unrouted |

Both boards are **placed but not routed**. Placement is machine-generated and then
meant to be refined by hand — decoupling is paired to its IC and connectors are
edge-anchored and rotated outward, but nothing is a substitute for a look in pcbnew.

Both carry pick-and-place **fiducials** (1 mm dot, 2 mm mask opening): three per
populated face, at three of the four corners. Never four — a symmetric set gives the
placement machine no way to tell a 180°-rotated panel from a correct one. The main
board has them on both faces; the optical head is single-sided so its back has none.

### Track widths

Net classes are set in each `.kicad_pro`, sized from IPC-2221 at 1 oz outer copper and
a 10 °C rise (0.20 mm ≈ 0.74 A, 0.50 mm ≈ 1.45 A, 0.80 mm ≈ 2.03 A):

| Class | Track | Nets |
|---|---|---|
| Default | 0.20 mm | everything else |
| Power | 0.50 mm | `+3V3` `SYS` `SYS_SW` `BAT` `USB_VBUS` `GND` |
| Switch | 0.80 mm | `U6-L1` `U6-L2` — main board only |
| USB | 0.20 mm | `D+`/`D-` both sides, diff pair 0.20/0.15 |
| Emitter | 0.80 mm | `SYS_SW` `D1-A` `D1-K` — head board only |

The emitter resistor is sized at the **top** of the SYS_SW range, not at the battery.
The BQ24075 regulates OUT to 5.5 V, so R18 is 3.9 Ω for about 0.49 A at a full cell and
about 0.90 A worst case — under D1's 1 A absolute maximum. At the old 3.0 Ω the USB case
reached roughly 1.1 A.

Two caveats. **Switch clearance stays at 0.20 mm**, not the 0.25 the wider track might
suggest: the TPS63031's WSON-10 places its own L1/L2 pads 0.20 mm from its thermal
pad, so anything stricter fails inside the package and no routing choice can fix it.
And the **USB numbers are not an impedance solution** — real 90 Ω differential needs
the fab's actual stackup. The ESP32-S3's native USB is Full Speed (12 Mbps), where
that matters far less than it would at High Speed.

### BalancerREF (HOBOVibe)

The main puck. ESP32-S3-MINI-1, IIS3DWB vibration sensor on SPI, LM1815 magnetic tach
front end, BQ24075 charger with an integrated dynamic power path, TPS63031 buck-boost, and a
1x05 header for an optional u-blox-class GPS used by the in-flight logging mode.

Two measurement profiles: **MR-VERT** uses an external isolated two-wire VR pickup;
**TR-VERT** uses the optical tach against retroreflective tape.

50 × 50 mm, four layers, components on both faces: ICs, connectors, switches and test
points on the front, passives on the back so each decoupling cap sits under its IC's
power pins. M2.5 mounting holes at the four corners, on a 43.40 × 42.90 mm rectangle
centred on the board. U1's antenna deliberately overhangs the top edge, which puts
almost all of its keepout off the board — the wide band still reaches 0.44 mm inside
the top edge, which is why the mounting-hole rectangle is 0.5 mm shorter than it is
wide. The overhang is required anyway, because the aluminium bracket must not sit
behind a PCB antenna.

The puck mounts **vertically, ESP32 to the left and USB-C to the right**. `UP` and
`LEFT` markers on the front silkscreen record that; with the board vertical the
accelerometer's vertical axis is in-plane (stiff) and the flexible out-of-plane axis
carries lateral instead. Which sensor channel that is still needs recording from
DS12569's orientation figure — firmware can also identify it at runtime, since the
vertical axis reads a static 1 g when the puck is mounted upright.

Three switches: SW1 power slide, SW2 acquire, SW3 boot. There is no reset button —
SW1 feeds U6's VIN and EN, so the power slide already power-cycles the MCU. SW1 is a
Würth WS-SLTV rated 300 mA switching; steady draw through it is about 180 mA, but BLE
TX bursts and switch-on inrush exceed that briefly. That is accepted as reduced switch
life rather than designed out — see DATASHEET-VERIFICATION.md.

**Sleep is not low power.** The LM1815 draws 3.6 mA typical (6 mA max) and sits on the
always-on 3V3 rail, as do the head's op-amp and comparator, so a sleeping puck draws
milliamps and a 500 mAh cell lasts days rather than months. If flight logging ever
depends on long sleeps, the fix is a load switch on the LM1815 and the head supply.

**Power path and charging.** A BQ24075 runs the input: it charges the cell and powers
the system from the same input independently, so charge termination is correct while
the puck is running, and it will run with a defective or absent pack. R3 (3.57 k)
sets fast charge to about 249 mA — 0.5C for a 500 mAh cell — and R35 (1.6 k) sets the
resistor-programmed input limit to about 1.0 A.

Four pins go to the MCU. `CHG_EN1` (GPIO5) and `CHG_EN2` (GPIO18) select the input
current limit; `PGOOD_N` (GPIO21) and `CHG_STAT` (GPIO38) are open-drain status inputs
with 100 k pull-ups, both **active low**. Two things are easy to get wrong here:

- The datasheet's current-limit table is indexed **(EN2, EN1)**, the reverse of the
  order the pins are named in.
- Both EN pins have 285 k internal pulldowns, so the limit is USB100 — **100 mA** —
  until firmware deliberately raises it.

`PGOOD_N` is the USB-present signal. Earlier revisions tried to infer that by comparing
two ADC dividers, because a single reading of `SYS_SW` cannot answer it: SYS was fed
either from USB through a Schottky or from the cell through a PFET, and the ranges
overlap. The BQ24075 arbitrates the input itself and simply reports the answer, so
Rev E deleted the second divider (`BAT_SENSE`, R33/R34/C31) along with its 500 k ADC
source impedance and its ~2 µA standing drain on the cell.

`SUPPLY_SENSE` (`SYS_SW/2` on GPIO12) survives as the supply-voltage reading. While the
puck runs unplugged the BQ24075 connects OUT to the battery, so it reads the cell; while
charging it reads the input-derived rail instead, not the cell. It is on ADC2_CH1, the
converter shared with the radio — worth knowing, because it is now the only supply
measurement on the board.

See [`BalancerREF/README.md`](BalancerREF/README.md) for the circuit description and
[`BalancerREF/DATASHEET-VERIFICATION.md`](BalancerREF/DATASHEET-VERIFICATION.md) for
every pin mapping checked against the manufacturer tables.

### BalancerREF_OptHead

The optical tach front end, split onto its own board on 2026-09-11. It mounts at 90° to
the main PCB on the second leg of an aluminium L-bracket, on a pivot bolt so the emitter
can be aimed at the tape. The split exists because neither optical part has leads to
form — the XPEBRD-L1 is a ceramic SMD LED and the BPW34S is the surface-mount BPW34 — so
they need their own copper.

The cut is deliberately placed **after** the comparator. The cable then carries only DC
rails and digital edges; cutting at the photodiode would have put the 10 kΩ
transimpedance summing junction on a flying lead beside a wire switching 500 mA at
20 kHz.

Connected to the main board by a 7-way cable (`J5` on both). Ground is interleaved
between the two digital lines: emitter-pulse crosstalk onto `OPT_COMP` arrives inside
the synchronous gating window by definition, so the detection logic cannot reject it and
it has to be stopped at the connector.

25 × 50 mm, two layers, **every part on the front** so B.Cu is an uninterrupted ground
pour. That is worth more than a clean optical face: the transimpedance summing node is
the highest-impedance point in the design and sits beside a wire switching 500 mA at
20 kHz. The cost is that the baffle and the red acrylic window have to clear the
electronics.

D1 sits centred on the optical axis with PD1 18 mm directly below it. **That spacing
and the lens keepout radius are estimates** — both are constants at the top of
`scripts/build_pcb.py` and should be set from the real Ledil TINA holder before anyone
commits to them. The spacing is the one that affects performance: it sets baffle depth
and the parallax back to the tape at the 18–24 in working range.

The B.Cu pour is written **unfilled** (KiCad's zone filler cannot be driven from
standalone pcbnew Python). KiCad fills it on open, or `Edit → Fill All Zones`.

## Verification

Both boards carry a connectivity checker that compares an exported netlist against
circuit specifications written by hand — exact net membership, so an unintended short, a
bypassed series part or a reversed two-terminal part fails rather than passing quietly.

```bash
# main board
cd BalancerREF
kicad-cli sch export netlist --format kicadsexpr -o review/BalancerREF.net BalancerREF.kicad_sch
python scripts/verify_netlist.py     # PASS: 49 exact circuit nets, 293 pin endpoints

# optical head
cd ../BalancerREF_OptHead
kicad-cli sch export netlist --format kicadsexpr -o review/OptHead.net BalancerREF_OptHead.kicad_sch
python scripts/verify_head.py        # PASS: 16 exact circuit nets, 63 pin endpoints
```

Each board has its own spec. The main board's covers everything except the optical
chain and asserts that *every* pin in the netlist belongs to some named net, so a
wrong connector pinout or a missed part fails rather than passing quietly. Run these
against a freshly exported netlist — a stale `.net` will report a green that means
nothing.

Both sheets pass ERC at **0 errors and 0 warnings**. Removing a part leaves the wires
that used to reach its pins, so `BalancerREF/scripts/fix_dangling_wires.py` sweeps those:
it removes a wire only when one end touches nothing at all, never removes a wire carrying
a label (labels attach to wire bodies, so that would silently split a net - trimming the
dead tail back to the label is the fix there), and exports the netlist before and after
to prove no pin changed net. It checks its own geometry against KiCad's ERC first and
aborts if the two disagree.

Generator scripts under `scripts/` are guarded and refuse to run without
`--overwrite-hand-layout`: both sheets were laid out by hand after generation, and the
`.kicad_sch` files are the source of truth.

## Revisions

Hardware revisions are marked with git tags rather than in filenames, so the KiCad
project names stay stable across revisions. `git tag` lists them; `git checkout revD`
gets that snapshot.

| Tag | Board state |
|---|---|
| `revC` | single board, optical front end on the main PCB, no layout |
| `revD` | optical head split out; SW4 and R5 dropped; BAT sense divider added; both boards placed |
| `revE` | MCP73831 + D2 + Q3 + R27 + R31 replaced by a BQ24075; BAT sense divider removed |
| `revF` | PD1 polarity fix; R18 3.9 ohm; U9 Schmitt NAND; switcher and TIA placement |

Rev D was defined by the **battery/supply sensing change** — `BAT_SENSE` on GPIO4
alongside `SUPPLY_SENSE`, to let firmware tell USB from battery. The board split and the
two part deletions rode along in the same revision.

Rev E is the **charge-management change**, and it removed Rev D's divider again: with a
BQ24075 arbitrating the input, `PGOOD` answers "am I on USB?" directly and the
two-divider comparison had nothing left to do. Five discrete parts went with it.

Rev F is the **repo-review revision** — no new function, but a set of corrections that
had to land before any copper is routed. One of them cleans up after Rev E: removing the
USB Schottky raised `SYS_SW`, which pushed the head's emitter resistor past D1's absolute
maximum current. The others are a logic part run outside its input-transition spec and
three placement problems, the worst being a 2.4 MHz switching loop routed through vias.
Rev F is also the first revision of the optical head since it was created, so that board
moves from Rev A to **Rev B**.

Rev F also carries the one outright **functional** defect found so far: PD1 was wired
with its anode on the transimpedance summing node, which sends the signal the wrong way
through two inverting stages and leaves the comparator unable to trip at any light level.
The optical tach could never have worked. Flipping the detector fixes it without changing
anything else; `BalancerREF/DATASHEET-VERIFICATION.md` traces the chain stage by stage,
including why the connectivity checkers passed the whole time — they prove the netlist
matches the intent, not that the intent works.

Two review items were checked and deliberately **not** changed — SW1's current rating
and U1's footprint. `BalancerREF/DATASHEET-VERIFICATION.md` records why, so they are not
re-raised at the next review.

## Not in this repo

Build output (`.pio/`, `build/`, `release/`), the firmware virtualenv, and the
point-in-time `*-backups/` and `archives/` zips are excluded — git tracks history
itself. Manufacturer datasheets in `BalancerREF/sources/` are included for reference
alongside the pin audits; `scripts/fetch_sources.py` re-fetches them from the URLs in
`sources/urls.json`.
