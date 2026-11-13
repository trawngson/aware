// The MPU-6050 under the plate (optional). Its own task reads it
// IMU_SAMPLE_HZ times a second on I2C port 0 and follows the plate: its tilt
// from level, whether it is still, and the jolt of anything landing on it
// (imu_math.h). While the chip is missing it looks for it every IMU_RETRY_MS,
// so the bin runs as before without one and picks it up once it answers.
//
// With the IMU in use (found, and not "imu off"):
// - a scan holds if the plate is off level at home (scan.cpp);
// - after a tip, the log says how far the plate tipped and whether it came
//   back level; the LED turns red if not;
// - the automatic scan weighs impacts with the camera (presence.h).
#pragma once

#include <Arduino.h>

#include "config.h"
#include "imu_math.h"

struct ImuReading {
  bool present = false;  // the chip answers
  imu::Vec3 accelG;      // the last sample
  imu::Vec3 gravityG;    // smoothed: the way down, for the tilt
  float tiltDeg = 0;     // from level ("imu level"), or from flat
  float shakeG = 0;
  float rotationDps = 0;
  bool still = false;
  uint32_t stillForMs = 0;
  float temperatureC = 0;
  uint32_t impacts = 0;  // counted since the chip was found
  uint32_t lastImpactMs = 0;
  float lastImpactPeakG = 0;
};

// Looks for the chip and starts the IMU task. setup(), after settings::load().
void imuBegin();

// Found and not "imu off": the checks above apply.
bool imuInUse();
bool imuPresent();
// "MPU-6050 at 0x68", or what it found.
String imuChipText();

ImuReading imuNow();

// Waits up to timeoutMs for the plate to be still for IMU_STILL_MS, and
// returns the reading either way (r.still says which). Worker only.
ImuReading imuSettle(uint32_t timeoutMs = IMU_SETTLE_MS);

// After "servo" or "angle": an "[imu] plate at ..." line, once it settles,
// so the angles can be set by the plate's real tilt. Worker only.
void imuReportTilt();

// The newest impact that no one has used yet, felt within IMU_FELT_WINDOW_MS.
struct Impact {
  float peakG;
  uint32_t ageMs;
};
bool imuUnusedImpact(Impact& impact);
// Uses up every impact so far: what landed has been dealt with.
void imuUseImpacts();

// "imu level": saves the way gravity points now as level. False, with the
// reason, when there is no chip, the plate isn't home or isn't still.
// Console only.
bool imuSaveLevel(String& why);
