// The board's RGB LED (WS2812) shows each scan's stage:
//   blue   an item was spotted (or BOOT, or "scan"): scanning
//   green  sorted: the servo turned to a bin
//   red    held: something failed and the servo stayed home
// Green and red stay on for LED_RESULT_MS, then the LED goes dark. Only the
// worker task drives it.
#pragma once

#include <cstdint>

enum class LedStage : uint8_t { Off, Scanning, Sorted, Error };

void ledBegin();
void ledShow(LedStage stage);
void ledUpdate();  // call often: turns a result off once its time is up
