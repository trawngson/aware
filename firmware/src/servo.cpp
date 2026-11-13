#include "servo.h"

#include <Arduino.h>

#include "config.h"
#include "console.h"
#include "imu.h"
#include "settings.h"

std::atomic<int> servoAngle{-1};
std::atomic<uint32_t> servoMovedAt{0};

namespace {

uint32_t dutyFor(int angle) {
  const uint32_t pulseUs =
      SERVO_MIN_PULSE_US + (SERVO_MAX_PULSE_US - SERVO_MIN_PULSE_US) * static_cast<uint32_t>(angle) / 180;
  const uint32_t maxDuty = (1u << SERVO_LEDC_BITS) - 1;
  return pulseUs * maxDuty / SERVO_PERIOD_US;
}

void writeServo(int angle) {
  ledcWrite(SERVO_PIN, dutyFor(angle));
  servoAngle = angle;
  servoMovedAt = millis();
}

}  // namespace

void servoBegin() {
  // A fixed channel keeps the servo off channel 0, which the camera clock uses.
  if (!ledcAttachChannel(SERVO_PIN, SERVO_FREQ_HZ, SERVO_LEDC_BITS, SERVO_LEDC_CHANNEL)) {
    say("[servo] could not set up the servo signal\n");
  }
  writeServo(settings::homeAngle);
}

void moveServo(int target) {
  target = constrain(target, 0, 180);
  const int from = servoAngle;
  const int speed = settings::servoSpeed;  // once: "speed" may change it mid-move
  if (from == target) return;
  if (from < 0 || speed <= 0) {
    if (from >= 0) say("[servo] %d -> %d\n", from, target);
    writeServo(target);
    return;
  }
  say("[servo] %d -> %d\n", from, target);
  const int steps = abs(target - from);
  const int direction = target > from ? 1 : -1;
  const uint32_t start = millis();
  for (int i = 1; i <= steps; ++i) {
    writeServo(from + direction * i);
    const uint32_t due = start + static_cast<uint32_t>(i) * 1000u / static_cast<uint32_t>(speed);
    while (static_cast<int32_t>(millis() - due) < 0) delay(1);
  }
}

void visit(int angle) {
  moveServo(angle);
  const uint32_t arrived = millis();
  imuReportTilt();
  while (millis() - arrived < DWELL_MS) delay(1);
  moveServo(settings::homeAngle);
}
