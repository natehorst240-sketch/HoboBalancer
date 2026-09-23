#pragma once
#include <cstddef>
#include <cstdint>

// Flight log on the "storage" SPIFFS partition: one JSON line per record, appended and
// flushed individually. Stops accepting records near capacity and never overwrites.
namespace storage {
constexpr double fullFraction = 0.95;
bool mount();                         // formats an empty partition on first use
bool mounted();
bool append(const char *line);        // false when full or on write failure; never partial
bool full();
uint32_t records();                   // lines currently stored
size_t used();
size_t total();
uint32_t writeFailures();
void sync();
bool erase();                         // deletes the log; refuse while acquiring
// Calls cb for every stored line (including the newline); returns false on read error.
bool stream(void (*cb)(const char *line, void *ctx), void *ctx);
}
