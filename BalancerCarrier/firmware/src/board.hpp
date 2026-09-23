#pragma once
// BalancerCarrier schematic. These are ESP32-S3 GPIO numbers, NOT FeatherS3 header
// pin numbers and NOT the module's silkscreen labels.
//
// !! NOT INTERCHANGEABLE WITH BalancerREF/firmware/src/board.hpp !!
// Twelve of the thirteen shared signals moved; only accelCs stayed on 17. Worse, the
// BalancerREF build's setupCharger() drives GPIO5 HIGH and GPIO18 LOW as outputs, and
// on this board those are the acquire button (a switch to GND) and the IIS3DWB's INT1
// (itself an output). Flashing a BalancerREF binary here shorts a driven output to
// ground when the button is pressed, and puts two drivers on DRDY. There is no charger
// on the carrier - the FeatherS3[D] owns charging - so that code is gone.
namespace board {

// ---- carrier signals, on the FeatherS3[D] headers --------------------------
constexpr int drdy=18,mag=1,opt=35,emitter=36,acquire=5,led=37;
constexpr int accelSck=12,accelMosi=11,accelMiso=14,accelCs=17; // IIS3DWB on SPI (4-wire, mode 3)
constexpr int gpsTx=10,gpsRx=7,gpsPps=6; // J4: UART TX->GPS RX, UART RX<-GPS TX, PPS in

// Sleep wake: EXT1 on mag (GPIO1) or acquire (GPIO5); the IIS3DWB has no wake-on-motion,
// so the tach pulse is the only automatic wake from a stopped rotor.
// BOTH must stay inside GPIO0-21. EXT1 can only be armed on an RTC GPIO, and the
// ESP32-S3 has 22 of them (CONFIG_SOC_RTCIO_PIN_COUNT). mag sat on GPIO33 until
// 2026-09-21, which is outside that range: pulse capture worked, rotor-spin wake
// silently did not. check_pinmap.py now asserts this.

// ---- module-internal, NOT on the headers -----------------------------------
// Fixed by the FeatherS3[D] itself, so they appear in no carrier netlist and
// check_pinmap.py validates them against these documented values rather than against
// the schematic. Source: unexpectedmaker/esp32s3, the MicroPython helper
// "code/micropython/helper libraries/feathers3/feathers3.py" (LDO2 = const(39),
// VBUS_SENSE = const(34)), cross-checked against
// series_d/schematics/schematic-feathers3d-p1.pdf.
//
//   ldo2       drives LDO2_EN through the IC1B AND gate into U3, an NCP167BMX330TBG
//              whose 3V3_2 output powers J4 pin 1 - the GPS. A 700 mA part, so the
//              GPS's ~25 mA is nothing. Its input is VBUS, which ORs USB (through D4)
//              and VBAT (through T2), so it works on battery. DEFAULT IS OFF: the GPS
//              stays dead until firmware raises this. It also feeds the module's RGB
//              LED and the second STEMMA connector, which go dark with it.
//   vbusSense  the module's own USB-present divider (R14 2K / R15 3K3 off VBUS).
//              Replaces BalancerREF's pgood: it reports that a USB source is attached,
//              which is what the status JSON actually used pgood for.
//   i2cSda,    the module's I2C bus. The MAX17048 fuel gauge sits on it at 0x36, and
//   i2cScl     so does the STEMMA QT connector. 10k pull-ups are already fitted on the
//              module, so do not enable internal ones.
constexpr int ldo2=39,vbusSense=34,i2cSda=8,i2cScl=9;

// ---- what the module owns, so there is no pin here for it ------------------
//   battery voltage and state of charge  MAX17048G+T10 fuel gauge on the module's own
//                                        I2C bus (IO8 SDA / IO9 SCL). Replaces
//                                        BalancerREF's supplyAdc divider on GPIO12.
//   charging                             no EN1/EN2/PGOOD/CHG pins exist here
//   USB                                  native on the module; no usbDm/usbDp

// ---- RESERVED - do not configure these as outputs --------------------------
//   IO0        the module's own boot button
//   IO3        strapping pin (JTAG source select)
//   IO43,IO44  UART0 console
//   IO8,IO9    I2C: the MAX17048 fuel gauge and the STEMMA QT connector
// SPARE: IO33, IO38. Neither is an RTC GPIO and neither is an ADC pin, so if a future
// signal needs deep-sleep wake or an analog read, neither spare will do.
}
