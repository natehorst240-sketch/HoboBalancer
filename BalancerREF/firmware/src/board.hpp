#pragma once
// BalancerREF schematic. These are GPIO numbers, NOT module pad numbers.
namespace board {
constexpr int drdy=6,mag=7,opt=8,emitter=9,acquire=10,led=11;
constexpr int accelSck=14,accelMosi=15,accelMiso=16,accelCs=17; // IIS3DWB on SPI (4-wire, mode 3)

// SYS_SW/2 on ADC2_CH1. Per SLUS810N, OUT is connected to VBAT whenever the input is
// out of range (and SYSOFF is low), so this reads the cell while running on battery.
// It does NOT read the cell while charging - OUT is then driven from IN - and it is
// not a USB-presence signal: use pgood for that.
// This is the only supply measurement on the board. BAT_SENSE was on GPIO4/ADC1_CH3
// and was removed with the BQ24075 swap, which leaves the reading on ADC2 - the unit
// shared with the radio. If a conversion here ever has to be trusted with the radio
// up, that is the constraint to design around.
constexpr int supplyAdc=12;

constexpr int usbDm=19,usbDp=20;
constexpr int gpsTx=1,gpsRx=2,gpsPps=13; // J4 GPS header: UART1 TX->GPS RX, UART1 RX<-GPS TX, PPS in

// BQ24075 charger with dynamic power path.
// EN1/EN2 select the input current limit. SLUS810N Table 7-2 indexes this table by
// (EN2, EN1) - note the order, it is the reverse of the names below, so write the two
// pins out rather than thinking in bit pairs:
//
//   EN2=0 EN1=0   100 mA   USB100
//   EN2=0 EN1=1   500 mA   USB500
//   EN2=1 EN1=0   set by RILIM (R35 = 1.6k -> 1610/1600 = about 1.0 A)
//   EN2=1 EN1=1   standby (USB suspend)
//
// Both pins have ~285 kOhm internal pull-downs, so the limit falls back to USB100
// whenever the MCU is not driving them - including before firmware starts. Raise it
// deliberately, and only after deciding what the attached port can actually supply:
// 500 mA out of a port that cannot source it is what VIN-DPM exists to survive, not a
// mode to sit in.
constexpr int chgEn1=5,chgEn2=18;

// Open-drain status outputs with 100 kOhm pull-ups on the board, both ACTIVE LOW:
//   pgood   low = a valid input source is present (this replaces the Rev D
//                 SYS_SW-versus-BAT comparison, which could not separate a weak USB
//                 port from a full cell)
//   chgStat low = charging in progress; high once charge terminates OR if the
//                 charger is disabled, so it is not by itself an input-present signal
constexpr int pgood=21,chgStat=38;

// Sleep wake: EXT1 on mag (GPIO7) or acquire (GPIO10); the IIS3DWB has no wake-on-motion.
}
