#pragma once
#include "flightlog.hpp"
#include <cstdint>

// J4 GPS module on UART1 (GPIO1 TX -> module RX, GPIO2 RX <- module TX), 8N1 NMEA, auto-baud 38400/9600.
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
