#pragma once
#include <cstddef>
void ble_start();
bool ble_connected();
void ble_send_line(const char *line); // communications task only; bounded retries
bool submit_command(const char *text, size_t length); // thread-safe, nonblocking
