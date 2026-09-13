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
| `BalancerREF/` | **HOBOVibe** — ESP32-S3 reference puck | **Rev C** | 50 × 50 mm, 4 layer, placed, unrouted |
| `BalancerREF_OptHead/` | Optical tach head | Rev A | 25 × 50 mm, 2 layer, placed, unrouted |

Both boards are **placed but not routed**. Placement is machine-generated and then
meant to be refined by hand — decoupling is paired to its IC and connectors are
edge-anchored and rotated outward, but nothing is a substitute for a look in pcbnew.

### BalancerREF (HOBOVibe)

The main puck. ESP32-S3-MINI-1, IIS3DWB vibration sensor on SPI, LM1815 magnetic tach
front end, MCP73831 charger with USB/battery power sharing, TPS63031 buck-boost, and a
1x05 header for an optional u-blox-class GPS used by the in-flight logging mode.

Two measurement profiles: **MR-VERT** uses an external isolated two-wire VR pickup;
**TR-VERT** uses the optical tach against retroreflective tape.

50 × 50 mm, four layers, components on both faces: ICs, connectors, switches and test
points on the front, passives on the back so each decoupling cap sits under its IC's
power pins. M2.5 mounting holes at the four corners. U1's antenna deliberately
overhangs the top edge, which moves its keepout off the board entirely — and is
required anyway, because the aluminium bracket must not sit behind a PCB antenna.

The puck mounts **vertically, ESP32 to the left and USB-C to the right**. `UP` and
`LEFT` markers on the front silkscreen record that; with the board vertical the
accelerometer's vertical axis is in-plane (stiff) and the flexible out-of-plane axis
carries lateral instead. Which sensor channel that is still needs recording from
DS12569's orientation figure — firmware can also identify it at runtime, since the
vertical axis reads a static 1 g when the puck is mounted upright.

Three switches: SW1 power slide, SW2 acquire, SW3 boot. There is no reset button —
SW1 feeds U6's VIN and EN, so the power slide already power-cycles the MCU.

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
python scripts/verify_netlist.py     # PASS: 43 exact circuit nets, 280 pin endpoints

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

Generator scripts under `scripts/` are guarded and refuse to run without
`--overwrite-hand-layout`: both sheets were laid out by hand after generation, and the
`.kicad_sch` files are the source of truth.

## Revisions

Hardware revisions are marked with git tags rather than in filenames, so the KiCad
project names stay stable across revisions. `git tag` lists them; `git checkout revC`
gets that snapshot.

## Not in this repo

Build output (`.pio/`, `build/`, `release/`), the firmware virtualenv, and the
point-in-time `*-backups/` and `archives/` zips are excluded — git tracks history
itself. Manufacturer datasheets in `BalancerREF/sources/` are included for reference
alongside the pin audits; `scripts/fetch_sources.py` re-fetches them from the URLs in
`sources/urls.json`.
