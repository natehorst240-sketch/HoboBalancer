#pragma once
#include <cstddef>
#include <cstdint>
#include <functional>

// The link to the carrier: bytes in, bytes out, no framing. The carrier speaks newline-delimited
// JSON on both BLE (Nordic UART Service, results fragmented into notifications of at most 180
// bytes) and a UART; the Protocol layer reassembles lines, so the UI never knows which link is
// in use. Implementations: BleCentral (NimBLE) and SerialLink (UART); both ESP-only.
namespace link {
enum class State : uint8_t { Off, Scanning, Connecting, Connected };

class Transport {
public:
    virtual ~Transport() = default;
    virtual bool begin() = 0;
    virtual State state() const = 0;
    // Send one complete command line including its trailing newline. False if not connected
    // or the line does not fit the link's write size (255 bytes for a BLE write).
    virtual bool send(const char *line, size_t length) = 0;
    // Called from the link's own task with raw received bytes; the receiver must copy them.
    void onBytes(std::function<void(const uint8_t *, size_t)> cb) { bytes_ = std::move(cb); }
    void onState(std::function<void(State)> cb) { state_ = std::move(cb); }
protected:
    std::function<void(const uint8_t *, size_t)> bytes_;
    std::function<void(State)> state_;
};
}  // namespace link
