# DogDoor

Automatic dog door. Nothing designed yet; this file holds the requirements and
the open decisions so they are not lost between sessions.

## Requirements (2026-09-25)

- Opens on a button press.
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

### Still to pin down before either can be sized

- Dog size, flap opening dimensions, flap weight and material.
- Mounting: wall, exterior door, or slider insert.
- What "button" means: a human button, a paw pad, or both; and whether close
  is on a timer, a second press, or a beam-break clear.
- Power source and whether it needs to work through an outage.

## Electronics

Plan to reuse the ESP32-S3 + ESP-IDF + PlatformIO stack from `BalancerCarrier/`
unless the project needs something it does not offer.
