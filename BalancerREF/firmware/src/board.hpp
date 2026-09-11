#pragma once
// BalancerREF schematic Rev C. These are GPIO numbers, NOT module pad numbers.
namespace board {
constexpr int drdy=6,mag=7,opt=8,emitter=9,acquire=10,led=11;
constexpr int accelSck=14,accelMosi=15,accelMiso=16,accelCs=17; // Rev C: IIS3DWB on SPI (4-wire, mode 3)
constexpr int supplyAdc=12; // ADC2_CH1: SYS_SW/2, NOT battery-only or USB presence.
constexpr int usbDm=19,usbDp=20;
constexpr int gpsTx=1,gpsRx=2,gpsPps=13; // J4 GPS header: UART1 TX->GPS RX, UART1 RX<-GPS TX, PPS in
// Sleep wake on Rev C: EXT1 on mag (GPIO7) or acquire (GPIO10); the IIS3DWB has no wake-on-motion.
}
