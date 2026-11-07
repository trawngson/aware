#include "status_led.h"

#include <Arduino.h>

#include "config.h"

namespace {

bool timed = false;  // a result (green or red) is showing
uint32_t offAt = 0;

void setColor(uint8_t red, uint8_t green, uint8_t blue) {
  rgbLedWrite(LED_PIN, red * LED_BRIGHTNESS / 255, green * LED_BRIGHTNESS / 255, blue * LED_BRIGHTNESS / 255);
}

}  // namespace

void ledBegin() { setColor(0, 0, 0); }

void ledShow(LedStage stage) {
  timed = stage == LedStage::Sorted || stage == LedStage::Error;
  offAt = millis() + LED_RESULT_MS;
  switch (stage) {
    case LedStage::Off: setColor(0, 0, 0); break;
    case LedStage::Scanning: setColor(0, 0, 255); break;
    case LedStage::Sorted: setColor(0, 255, 0); break;
    case LedStage::Error: setColor(255, 0, 0); break;
  }
}

void ledUpdate() {
  if (timed && static_cast<int32_t>(millis() - offAt) >= 0) {
    timed = false;
    setColor(0, 0, 0);
  }
}
