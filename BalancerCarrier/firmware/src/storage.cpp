#include "storage.hpp"
#include <cerrno>
#include <cstdio>
#include <cstring>
extern "C" {
#include "esp_spiffs.h"
#include "unistd.h"
}

namespace {
constexpr char label[] = "storage";
constexpr char base[] = "/log";
constexpr char path[] = "/log/flight.jsonl";
bool isMounted = false, isFull = false;
uint32_t lineCount = 0, failures = 0;
size_t usedBytes = 0, totalBytes = 0;
FILE *out = nullptr;

void refresh() {
    size_t t = 0, u = 0;
    if (esp_spiffs_info(label, &t, &u) == ESP_OK) { totalBytes = t; usedBytes = u; }
    isFull = totalBytes && double(usedBytes) >= storage::fullFraction * double(totalBytes);
}

void countLines() {
    lineCount = 0;
    FILE *f = std::fopen(path, "r");
    if (!f) return;
    int c;
    while ((c = std::fgetc(f)) != EOF) if (c == '\n') ++lineCount;
    std::fclose(f);
}
}  // namespace

namespace storage {
bool mount() {
    if (isMounted) return true;
    esp_vfs_spiffs_conf_t conf{};
    conf.base_path = base; conf.partition_label = label; conf.max_files = 3; conf.format_if_mount_failed = true;
    if (esp_vfs_spiffs_register(&conf) != ESP_OK) return false;
    isMounted = true;
    refresh();
    countLines();
    return true;
}
bool mounted() { return isMounted; }

bool append(const char *line) {
    if (!isMounted) return false;
    refresh();
    if (isFull) return false;
    if (!out) out = std::fopen(path, "a");
    if (!out) { ++failures; return false; }
    const size_t n = std::strlen(line);
    if (std::fwrite(line, 1, n, out) != n || std::fflush(out) != 0) {
        // ENOSPC or media error: close so nothing half-written is extended later.
        ++failures;
        std::fclose(out); out = nullptr;
        refresh();
        if (errno == ENOSPC) isFull = true;
        return false;
    }
    fsync(fileno(out));
    ++lineCount;
    usedBytes += n;
    return true;
}

bool full() { return isFull; }
uint32_t records() { return lineCount; }
size_t used() { return usedBytes; }
size_t total() { return totalBytes; }
uint32_t writeFailures() { return failures; }
void sync() { if (out) { std::fflush(out); fsync(fileno(out)); } }

bool erase() {
    if (!isMounted) return false;
    if (out) { std::fclose(out); out = nullptr; }
    const int r = std::remove(path);
    lineCount = 0;
    refresh();
    isFull = false;
    return r == 0 || errno == ENOENT;
}

bool stream(void (*cb)(const char *, void *), void *ctx) {
    if (!isMounted) return false;
    sync();
    FILE *f = std::fopen(path, "r");
    if (!f) return true;  // nothing stored yet
    static char line[640];
    while (std::fgets(line, sizeof(line), f)) {
        const size_t n = std::strlen(line);
        if (!n || line[n - 1] != '\n') continue;  // truncated tail from a power loss: skip
        cb(line, ctx);
    }
    const bool ok = !std::ferror(f);
    std::fclose(f);
    return ok;
}
}  // namespace storage
