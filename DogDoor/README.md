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

### Still to pin down

- Flap material (sets mass and whether it needs a counterbalance).
- Mounting: wall, exterior door, or slider insert.
- Power source and whether it needs to work through an outage.

## Electronics

Plan to reuse the ESP32-S3 + ESP-IDF + PlatformIO stack from `BalancerCarrier/`
unless the project needs something it does not offer.
