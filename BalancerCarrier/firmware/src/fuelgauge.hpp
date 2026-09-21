#pragma once
// MAX17048G+T10 battery fuel gauge, on the FeatherS3[D]'s own I2C bus.
//
// Replaces BalancerREF's supplyAdc divider. That read SYS_SW/2 on ADC2_CH1 - the ADC
// unit shared with the radio - and could only infer the cell voltage while running on
// battery, never while charging. This measures the cell directly and reports state of
// charge, which a divider cannot do at all.
//
// Every accessor returns NAN (or false) rather than a stale or invented figure when
// the part has not answered, so a missing gauge degrades the status report instead of
// silently reporting a healthy battery.
namespace fuelgauge {

// Brings up the I2C bus and probes for the device. Safe to call once at startup;
// returns false if the gauge does not answer, after which every reading is NAN.
bool setup();

bool present();          // did setup() find the device
double cellVolts();      // battery terminal voltage, NAN if unavailable
double stateOfCharge();  // percent 0-100, NAN if unavailable
double chargeRate();     // percent per hour, signed; positive means charging

// chargeRate() above a small positive threshold. Unlike BalancerREF's chgStat pin this
// is a measurement, not a charger status line, so it stays true only while the cell is
// actually gaining charge - it goes false at termination without needing a separate
// "charge complete" case.
bool charging();

}
