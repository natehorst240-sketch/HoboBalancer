#pragma once
#include "flightlog.hpp"
#include <cstdint>

// J4 GPS module on UART1 (GPIO10 TX -> module RX, GPIO7 RX <- module TX), 8N1 NMEA,
// auto-baud 38400/9600.
//
// MODULE: Adafruit Ultimate GPS Breakout, PA1616S (product 746). Verified against
// Adafruit's product page and pinout guide on 2026-09-21:
//   Vin 3.0-5.5 V      LDO2_OUT supplies 3.3 V, so this is in range with 0.3 V to spare
//   3 V logic out      direct to the ESP32-S3, no level shifting
//   9600 baud default  already the second entry in the auto-baud list below
//   PPS                pulses high 3.3 V for 50-100 ms once per second, on fix
//   20 mA tracking / 25 mA acquisition
// Only four pins are required - VIN, GND, TX, RX - so J4's five cover those plus PPS.
// The board's EN pin is left unused: LDO2 gates the whole rail, which removes the load
// rather than idling it. The pin numbers in this comment were BalancerREF's (GPIO1/GPIO2)
// until 2026-09-21 - on the carrier GPIO1 is MAG_TACH, so that comment was worse than
// none. The code itself takes board::gpsTx / board::gpsRx and was always correct.
//
// The carrier's rail is switched: J4 pin 1 is LDO2_OUT, so call setGpsPower(true)
// before start() or the module is simply unpowered and present() stays false.
//
// PPS is wired to board::gpsPps on the carrier but NOTHING READS IT YET. It exists so
// the hardware is there when time discipline is wanted; until something captures it,
// the pin is an unused input.
namespace gps {
void start();                         // install UART1 and the reader task; safe if no module is fitted
flight::Fix latest();                 // copy of the most recent fix
uint32_t fixSequence();               // increments on every accepted RMC/GGA sentence
uint32_t sentences();
uint32_t rejected();
bool present();                       // any valid sentence in the last 5 s
int baud();                           // baud currently in use by the auto-baud reader
void sleep();                         // u-blox UBX-RXM-PMREQ backup and Quectel PMTK161 standby; wake on UART RX
}
