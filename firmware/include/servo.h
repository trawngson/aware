// The servo that tips the plate, on SERVO_PIN. Worker only, after
// servoBegin() in setup().
#pragma once

#include <atomic>
#include <cstdint>

// The angle last sent to the servo, -1 before the first. The console reads it
// for "status".
extern std::atomic<int> servoAngle;
// millis() of the last step sent to the servo. The IMU ignores the jolts of
// the servo's own starts and stops for a moment after it.
extern std::atomic<uint32_t> servoMovedAt;

// Sets up the servo signal and sends the servo home.
void servoBegin();

// Ramps one degree at a time at the saved speed ("speed"); 0 jumps straight
// there and lets the servo move at its own top speed.
void moveServo(int target);

// Turns to the angle, holds there DWELL_MS, and goes back home.
void visit(int angle);
