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
bottom, RFID collar or microchip to unlock (current lean, 2026-09-25)**
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
0.032 in 2024-T3 aluminium, alodined and painted. Estimates for 12 x 12 in
with a 1/2 in core (core thickness not yet fixed):

| Part | Mass |
|---|---|
| 1/8 in plywood skin, each | ~0.19 kg |
| 0.032 in 2024-T3 skin, each | ~0.21 kg |
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

### Still to pin down

- Foam core thickness, and whether both faces get aluminium.
- Mounting: wall, exterior door, or slider insert.
- Power source and whether it needs to work through an outage.

## Electronics

Plan to reuse the ESP32-S3 + ESP-IDF + PlatformIO stack from `BalancerCarrier/`
unless the project needs something it does not offer.
