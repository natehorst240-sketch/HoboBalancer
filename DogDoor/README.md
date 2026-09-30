# DogDoor

Automatic dog door. Nothing designed yet; this file holds the requirements and
the open decisions so they are not lost between sessions.

## Requirements (2026-09-25)

- Opens on a paw or nose "boop" button. One on each side of the door.
- Flap opening 12 x 12 in (305 x 305 mm).
- An IoT "away" switch disables the door remotely while nobody is home.
- The door must keep working normally with no network. The network only sets or
  clears the away lockout; it is never in the path of a normal open/close.
- Obstruction detection: the door must never close hard on a dog. Whatever the
  actuator is, it needs a stall/current/force limit and a retry-open on block.
- Defined behaviour on power loss (open, closed, or stays where it is) is a
  decision to make, not an accident of the mechanism.

## Open decisions

### Actuator: vertical slide vs side hinge

**A. Vertical slide (guillotine) on CNC linear rails, stepper driven**
- Flap seals well against a flat frame with brush strip; no swing clearance needed.
- A lead screw with a fine enough pitch is self-locking, so the stepper can be
  de-energised when idle and the flap stays put. A belt drive is not, and the
  flap would drop on power loss.
- Guillotine pinch hazard is the main risk. A TMC2209-class driver gives stall
  detection (StallGuard) and sensorless homing, which covers both obstruction
  detection and the end stop, but it must be tuned and tested on the real flap.
- Rails, screw and carriage are exposed to dirt and weather; needs covering.

**B. Side hinge, motorised, with magnetic hold-closed and release**
- Fewer precision parts; easier to build and repair.
- Needs swing clearance and is wind-loaded when open.
- If the flap is driven through a gearbox, the dog cannot push it and a stall
  loads the gears; a clutch or a motor that can be back-driven avoids that.
- Hold-closed options: permanent-magnet catch the motor pulls off, or an
  electromagnet (maglock) which is fail-open on power loss unless backed up.
- Sealing a hinged flap around all four edges is harder than a sliding one.

### First-pass sizing for the slide (estimates, not measured)

Flap mass for a 12 x 12 in panel, from bulk density only:

| Material | Mass |
|---|---|
| 1/4 in polycarbonate | ~0.7 kg |
| 3/8 in polycarbonate | ~1.1 kg |
| 1/2 in HDPE | ~1.1 kg |
| 1/8 in aluminium | ~0.8 kg |

So the moving load is roughly 1 to 2 kg with the carriage, about 10 to 20 N.
Any NEMA 17 has torque to spare for that; the constraints are speed and
holding, not force.

Travel is about 330 mm (opening plus overlap). Lead screw travel time:

| Lead | 300 rpm | 600 rpm |
|---|---|---|
| 2 mm (T8x2, single start) | 33 s | 17 s |
| 4 mm (T8x4) | 17 s | 8 s |
| 8 mm (T8x8, four start) | 8 s | 4 s |

The common cheap "T8" screw is T8x8, which is *not* self-locking: the flap
will drop on power loss and the stepper must hold it when open. T8x2 is
self-locking but too slow for a dog waiting at the door. The way out is to
counterbalance the flap (weight over a pulley, or a constant-force spring) so
the net load is near zero; then an 8 mm lead or even a belt is fine, and a
power-loss drop is gentle. Decide this before buying the screw.

Rails: 8 mm rods with LM8UU bearings are enough for this load and travel.
MGN12 rails are stiffer and better sealed but cost more; either works.

### Button and close logic

- Nose/paw button: a large sealed mechanical button (100 mm arcade style, or
  a pressure mat for paw). Capacitive touch is a poor fit for wet noses, fur
  and rain.
- Closing on a timer alone is not safe. Add an IR beam-break across the
  opening; close only after the beam has been clear for a few seconds, and
  re-open if it breaks while closing. Stall detection stays as the backstop.

**C. Passive bi-directional top-hinged flap, electrically released catch at the
bottom, RFID collar or microchip to unlock (lean on 2026-09-25, superseded by D)**
- No actuator moves the flap, so no pinch hazard, no rails, no stall tuning.
  The electronics only decide locked or unlocked.
- A bought flap with its own magnets and brush seal handles wind and rattle;
  the project supplies the latch, the reader and the controller.
- Catch: a latch bar at the bottom that blocks the flap in both directions.
  Prefer a small motor or servo-moved latch (zero power to hold, fail state is
  a design choice) over an electromagnet, which draws current the whole time
  it holds and is fail-open on power loss.
- Reader: LF RFID, 125 kHz for a collar tag or 134.2 kHz FDX-B (ISO 11784/5)
  for the dog's implanted microchip, which removes the collar entirely. Read
  range is a few cm to ~15 cm, so the antenna coil goes around the tunnel and
  the dog unlocks it by putting its head to the flap. That short range is a
  feature: it proves the dog is at the door, which BLE or UHF cannot.
- The boop button becomes optional; the head-at-flap gesture replaces it.
- Away lockout is trivial: latch stays engaged regardless of tag reads.
- Cannot tell in from out with one antenna; add a second if that matters.

**D. Motorised side-hinged panel over the tunnel, Pawport style (current lean,
2026-09-30)**

The 12 x 12 in sandwich panel hangs on a vertical hinge at one side of a
frame mounted on the inside of the tunnel, and a motor at the hinge swings it
inward 90 to 120 degrees. This is the mechanism the user wants to build.

Torque budget for the ~0.8 kg panel (estimates):

| Load | Torque at hinge |
|---|---|
| Inertia, open 90 deg in 1.5 s | ~0.07 Nm |
| Gravity from a 5 deg hinge-tilt install error | ~0.1 Nm |
| Wind 10 m/s (22 mph) on the open panel | ~1.0 Nm |
| Wind 15 m/s (34 mph) | ~2.4 Nm |
| Wind 20 m/s (45 mph) | ~4.2 Nm |

Inertia is nothing; wind and seal friction set the motor. Inward swing keeps
the open panel out of most wind, so 2 to 3 Nm (20 to 30 kgf.cm) at the hinge
is the target, with the closed hold coming from magnets or the latch bar, not
the motor.

Drive layout, in order of preference:

1. Bus servo coaxial with the hinge. Serial servos in the 30 to 60 kgf.cm
   class report position, load and temperature and accept a torque limit, so
   pinch protection is a setting: the panel stops and backs off when load
   exceeds the limit. Add a friction slip clutch between servo and hinge so a
   dog shoving the panel cannot strip the gearbox and the door can be pushed
   by hand with power off.
2. NEMA 17 stepper with a 5:1 planetary gearbox and a TMC2209 driver, using
   StallGuard for obstruction detection. More parts, but the driver and the
   tuning are already familiar from option A.
3. Geared DC motor with encoder and current sensing. Cheapest motor, most
   firmware.

Drive decided 2026-09-30: bus servo, coaxial with the hinge, with a slip
clutch. What that fixes:

- Servo class: serial bus (half-duplex TTL UART, one wire for data plus
  power) with position, load and temperature readback and a settable torque
  limit. Target 30 to 60 kgf.cm at the hinge. Candidates to check against
  current datasheets, not to buy on this note: Feetech STS/SMS series,
  Hiwonder HTD series, Dynamixel X series. Verify stall torque at the supply
  voltage you will actually run, rated angle range (needs 120 deg plus
  margin, most give 240 to 360), and whether load readback is real current or
  an estimate.
- Supply: most of these want 7.4 or 12 V nominal. Plan the door supply
  around the servo, and give it its own rail with a bulk capacitor; a stalled
  servo pulls several amps.
- Interface: ESP32-S3 UART with a direction pin, or a tri-state buffer, for
  half-duplex. The ESP-IDF UART driver handles this; no extra controller.
- Mount: servo body fixed to the frame, output horn to the clutch input,
  clutch output to the hinge pin. The panel's hinge load must go through a
  real bearing on the frame, not through the servo output bearing.
- Torque limit is the primary pinch protection, the clutch is the mechanical
  backstop, and the hinge encoder is the truth for panel angle.

Sensors: absolute magnetic encoder (AS5600 class) on the hinge axis, so panel
angle is known independently of the motor and slip clutch; IR beam-break in
the tunnel; Hall closed-sensor as in option C. Obstruction rule: commanded
angle and encoder angle diverge, or servo load exceeds the limit, -> stop,
reverse a few degrees, retry after the beam clears.

Frame: covers the tunnel on the inside, carries the hinge, the servo, the
magnet or latch strike and brush seal on the three free edges. Pawport keeps
the panel indoors for the same reason: weather and wind stay outside.

Unlock trigger stays as option C: LF RFID at the tunnel, away flag from the
network, boop button optional.

### Latch logic (option C)

Inputs: a closed-flap sensor (magnet on the flap, reed or Hall sensor in the
frame, aligned only when the flap hangs centred), the RFID reader, and the
away flag from the network.

- LATCHED: bar extended, flap pinned. Tag read and not away -> retract bar,
  go to OPEN.
- OPEN: bar retracted, flap swings freely. Start the settle timer only
  when the flap sensor reads aligned *and* no tag has been read for the same
  window. Any misalignment or tag read restarts the timer. Timer expires ->
  extend bar, go to LATCHED.
- AWAY: same as OPEN but tag reads are ignored, so the bar goes in at the
  next 5 s of settled flap and stays in until the away flag clears.

The settle time is a hard minimum of 5 s. Its purpose is to outlast the
flap's swing after a dog passes, so the bar never drives out while the flap is
still oscillating. Do not shorten it; it may need to grow if a heavier flap
swings longer.

Rules that fall out of this:

- Never extend the bar unless the flap sensor reads aligned; otherwise the bar
  jams on the flap edge.
- The settle timer must include "no tag in range". Without that, a dog that
  stands at the door without pushing through gets pinned out after 5 s.
- Confirm the bar reached its end (limit switch or current sense). If it did
  not, retract and retry rather than sit half-engaged.
- Drive the bar with a MOSFET or servo signal, not a mechanical relay; it
  cycles many times a day.
- Power-loss state is set by the latch mechanism: a spring-return solenoid
  picks one state, a servo mostly stays put. Decide which; "unlocked" is the
  safer default for a dog outside in weather.

### Flap (decided 2026-09-25)

Sandwich panel: two 1/8 in plywood skins over a foam core, exterior face
0.032 in aluminium, alodined and painted (alloy: see below). Estimates for 12 x 12 in
with a 1/2 in core (core thickness not yet fixed):

| Part | Mass |
|---|---|
| 1/8 in plywood skin, each | ~0.19 kg |
| 0.032 in aluminium skin, each | ~0.21 kg |
| 1/2 in foam core | ~0.04 kg |
| Whole flap, one aluminium face | ~0.7 kg |
| Whole flap, both faces | ~0.9 kg |

Thickness with one aluminium face is ~0.8 in, thicker than a bought pet flap,
so the hinge, brush seal and latch bar are sized to this flap, not bought.

- Foam does not hold fasteners: put a hardwood or aluminium edge insert where
  the hinge pins, the magnets and the latch strike go.
- The aluminium skin sits in the plane of the tunnel and will detune and
  shield an LF RFID coil mounted in the frame around it. Keep the antenna in a
  non-metal bezel standing proud of the flap plane on the dog's side, and
  test read range against the finished flap before fixing the design.
- A heavier flap swings longer; re-check the 5 s settle minimum on the real
  panel.

Alternative core: a 3D-printed plug wrapped in the same 0.032 in aluminium.
Estimates for a 1/2 in thick printed core:

| Core | Core mass | One al face | Both faces |
|---|---|---|---|
| PETG, 10% infill, 2 walls | ~0.26 kg | ~0.5 kg | ~0.7 kg |
| PETG, 15% infill, 3 walls | ~0.35 kg | ~0.6 kg | ~0.8 kg |

Roughly the same weight as ply-and-foam; the mass is in the aluminium either
way. What the printed core buys is integrated features: magnet pockets, hinge
bosses, the latch strike and a fastener-holding edge all printed in, which
removes the edge-insert problem. Costs and cautions:

- 305 mm square needs a 300 mm+ bed, or the core prints in sections and joins.
- A dark painted aluminium face in sun gets hot enough to soften PLA. Use
  PETG or ASA for the core, and keep the paint light if it faces the sun.
- Skin alloy changed to 5052 (2026-09-26) so the edges can be wrapped; 2024-T3
  was dropped for its poor bend formability. Mass is the same within a few
  grams. Alodine and paint apply to 5052 as before. Confirm the temper (H32 is
  the usual sheet) and its bend radius for 0.032 in from a bend table.
- Same RFID shielding caution as above; the skin is what matters, not the core.

### Still to pin down

- Core: ply-and-foam or printed plug; core thickness; one or both faces aluminium.
- Mounting: wall, exterior door, or slider insert.
- Power source and whether it needs to work through an outage.

## Prior art (checked 2026-09-30)

- Pawport (pawport.com): motorised panel that retrofits over an existing pet
  door, opens to 90 or 120 degrees, collar tag with app-adjustable range and
  1+ year battery, $699 to $849. Tag radio is not stated on their site.
- jchirayath/PetDoor (github): ESP32 listens for a BLE beacon on the collar
  and pulses relays across the buttons of a bought motorised coop door. About
  $80. Author's own caveats: RSSI is a poor distance sensor, BLE beacons are
  unauthenticated, and the firmware has no obstruction detection.
- s60sc/ESP32_RFID_Reader (github): FDX-B 134.2 kHz pet microchip and EM4100
  decoder for ESP32. Directly relevant to the option C reader.

## Electronics

Plan to reuse the ESP32-S3 + ESP-IDF + PlatformIO stack from `BalancerCarrier/`
unless the project needs something it does not offer.
