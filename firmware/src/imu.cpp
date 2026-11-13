#include "imu.h"

#include <Wire.h>

#include <atomic>
#include <cstring>

#include "config.h"
#include "console.h"
#include "servo.h"
#include "settings.h"

namespace {

// MPU-6050 registers (register map rev 4.2).
constexpr uint8_t REG_SMPLRT_DIV = 0x19;
constexpr uint8_t REG_CONFIG = 0x1A;
constexpr uint8_t REG_GYRO_CONFIG = 0x1B;
constexpr uint8_t REG_ACCEL_CONFIG = 0x1C;
constexpr uint8_t REG_ACCEL_XOUT_H = 0x3B;
constexpr uint8_t REG_PWR_MGMT_1 = 0x6B;
constexpr uint8_t REG_WHO_AM_I = 0x75;

constexpr uint8_t kReset = 0x80;
constexpr uint8_t kClockGyroX = 0x01;  // awake, on the X gyro's clock (steadier than the internal one)
constexpr uint8_t kFilter94Hz = 0x02;  // DLPF_CFG 2: accel 94 Hz, gyro 98 Hz, 1 kHz internal rate
constexpr uint8_t kGyro500 = 0x08;     // +-500 deg/s
constexpr uint8_t kAccel4g = 0x08;     // +-4 g: room for a hard landing, fine enough for the tilt
constexpr float kGyroLsbPerDps = 65.5f;
constexpr float kAccelLsbPerG = 8192;
constexpr uint8_t kAddresses[] = {0x68, 0x69};  // AD0 low (most modules) or high
constexpr int kMissesBeforeLost = 5;            // failed reads in a row

portMUX_TYPE lock = portMUX_INITIALIZER_UNLOCKED;
// Under lock.
ImuReading shared;
imu::Vec3 level;
bool haveLevel = false;
char chipText[48] = "";

std::atomic<bool> present{false};
std::atomic<uint32_t> usedImpacts{0};
uint8_t address = 0;  // IMU task only, once it runs

bool answers(uint8_t addr) {
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;  // a probe: quiet when nothing answers
}

bool writeRegister(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(address);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

bool readRegisters(uint8_t reg, uint8_t* out, size_t count) {
  Wire.beginTransmission(address);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(address, count) != count) return false;
  for (size_t i = 0; i < count; ++i) out[i] = Wire.read();
  return true;
}

// The WHO_AM_I answers of the MPU-6050 and the chips sold as one. They all
// keep these registers where the MPU-6050 has them.
const char* chipName(uint8_t id) {
  switch (id) {
    case 0x68: return "MPU-6050";
    case 0x70: return "MPU-6500";
    case 0x71: return "MPU-9250";
    case 0x73: return "MPU-9255";
  }
  return nullptr;
}

// Finds the chip and sets it up: 200 samples a second through the 94 Hz
// filter, +-4 g and +-500 deg/s. Before the IMU task runs, or in it.
bool findChip() {
  for (const uint8_t candidate : kAddresses) {
    if (!answers(candidate)) continue;
    address = candidate;
    uint8_t id = 0;
    if (!readRegisters(REG_WHO_AM_I, &id, 1) || !writeRegister(REG_PWR_MGMT_1, kReset)) continue;
    delay(100);
    if (!writeRegister(REG_PWR_MGMT_1, kClockGyroX) || !writeRegister(REG_CONFIG, kFilter94Hz) ||
        !writeRegister(REG_SMPLRT_DIV, 1000 / IMU_SAMPLE_HZ - 1) || !writeRegister(REG_GYRO_CONFIG, kGyro500) ||
        !writeRegister(REG_ACCEL_CONFIG, kAccel4g)) {
      continue;
    }
    char text[sizeof(chipText)];
    const char* name = chipName(id);
    if (name) {
      snprintf(text, sizeof(text), "%s at 0x%02x", name, address);
    } else {
      snprintf(text, sizeof(text), "MPU-6050 look-alike (id 0x%02x) at 0x%02x", id, address);
    }
    portENTER_CRITICAL(&lock);
    memcpy(chipText, text, sizeof(chipText));
    portEXIT_CRITICAL(&lock);
    uint8_t range = 0;
    if (readRegisters(REG_ACCEL_CONFIG, &range, 1) && (range & 0x18) != kAccel4g) {
      say("[imu] the chip didn't keep its range setting (reads 0x%02x): its g readings may be off\n", range);
    }
    return true;
  }
  return false;
}

imu::Tuning tuning() {
  imu::Tuning t;
  t.sampleHz = IMU_SAMPLE_HZ;
  t.stillG = IMU_STILL_G;
  t.impactG = IMU_IMPACT_G;
  t.rearmG = IMU_REARM_G;
  t.impactGapMs = IMU_IMPACT_GAP_MS;
  return t;
}

void publish(const imu::Tracker& tracker, const imu::Sample& s, uint32_t impacts, uint32_t nowMs) {
  ImuReading r;
  r.present = true;
  r.accelG = s.accelG;
  r.gravityG = tracker.gravity();
  r.shakeG = tracker.shakeG();
  r.rotationDps = tracker.rotationDps();
  r.still = tracker.still();
  r.stillForMs = tracker.stillForMs(nowMs);
  r.temperatureC = s.temperatureC;
  r.impacts = impacts;
  r.lastImpactMs = tracker.lastImpactMs();
  r.lastImpactPeakG = tracker.lastImpactPeakG();
  portENTER_CRITICAL(&lock);
  const imu::Vec3 levelNow = level;
  const bool levelSaved = haveLevel;
  portEXIT_CRITICAL(&lock);
  r.tiltDeg = imu::tiltDegrees(r.gravityG, levelNow, levelSaved);
  portENTER_CRITICAL(&lock);
  shared = r;
  portEXIT_CRITICAL(&lock);
}

void markMissing() {
  present = false;
  portENTER_CRITICAL(&lock);
  shared.present = false;
  portEXIT_CRITICAL(&lock);
}

// Reads the chip every 1/IMU_SAMPLE_HZ s; while it is missing, looks for it
// every IMU_RETRY_MS. It prints only when the chip comes or goes, so a busy
// console never makes it miss samples.
void imuTask(void*) {
  imu::Tracker tracker(tuning());
  uint32_t impacts = 0;  // across finds, so a used-up count never runs ahead
  int misses = 0;
  TickType_t wake = xTaskGetTickCount();
  const TickType_t period = pdMS_TO_TICKS(1000 / IMU_SAMPLE_HZ);
  for (;;) {
    if (!present) {
      vTaskDelay(pdMS_TO_TICKS(IMU_RETRY_MS));
      if (!findChip()) continue;
      tracker = imu::Tracker(tuning());
      misses = 0;
      usedImpacts = impacts;
      present = true;
      say("[imu] found the %s\n", imuChipText().c_str());
      wake = xTaskGetTickCount();
    }
    vTaskDelayUntil(&wake, period);
    uint8_t raw[14];
    if (!readRegisters(REG_ACCEL_XOUT_H, raw, sizeof(raw))) {
      if (++misses >= kMissesBeforeLost) {
        markMissing();
        say("[imu] lost the %s: running without it until it answers again\n", imuChipText().c_str());
      }
      continue;
    }
    misses = 0;
    const uint32_t now = millis();
    const imu::Sample sample = imu::decode(raw, kAccelLsbPerG, kGyroLsbPerDps);
    // The servo's own starts and stops jolt the plate: they aren't items.
    const bool countImpacts =
        servoAngle == settings::homeAngle && now - servoMovedAt.load() >= IMU_AFTER_MOVE_MS;
    if (tracker.update(sample, now, countImpacts)) ++impacts;
    publish(tracker, sample, impacts, now);
  }
}

}  // namespace

void imuBegin() {
  haveLevel = settings::haveImuLevel;
  level = settings::imuLevel;
  if (!Wire.begin(IMU_PIN_SDA, IMU_PIN_SCL, IMU_I2C_HZ)) {
    say("[imu] could not set up I2C on GPIO %d and %d: running without the IMU\n", IMU_PIN_SDA, IMU_PIN_SCL);
    return;
  }
  Wire.setTimeOut(20);
  if (findChip()) {
    present = true;
    say("[imu] %s, %s\n", imuChipText().c_str(),
        settings::imuOn ? (haveLevel ? "level saved" : "no level saved yet: \"imu level\"") : "off (\"imu on\")");
  } else {
    say("[imu] none on GPIO %d (SDA) and %d (SCL): running without it, and looking for one every %u s\n",
        IMU_PIN_SDA, IMU_PIN_SCL, static_cast<unsigned>(IMU_RETRY_MS / 1000));
  }
  // Above the console and worker: it does little, but on time.
  xTaskCreatePinnedToCore(imuTask, "bin-imu", IMU_TASK_STACK_BYTES, nullptr, 3, nullptr, xPortGetCoreID());
}

bool imuPresent() { return present; }

bool imuInUse() { return present && settings::imuOn; }

String imuChipText() {
  char text[sizeof(chipText)];
  portENTER_CRITICAL(&lock);
  memcpy(text, chipText, sizeof(text));
  portEXIT_CRITICAL(&lock);
  return text;
}

ImuReading imuNow() {
  portENTER_CRITICAL(&lock);
  const ImuReading r = shared;
  portEXIT_CRITICAL(&lock);
  return r;
}

ImuReading imuSettle(uint32_t timeoutMs) {
  const uint32_t start = millis();
  ImuReading r = imuNow();
  while (r.present && r.stillForMs < IMU_STILL_MS && millis() - start < timeoutMs) {
    delay(5);
    r = imuNow();
  }
  return r;
}

void imuReportTilt() {
  if (!imuInUse()) return;
  const ImuReading r = imuSettle();
  if (r.present) say("[imu] plate at %.1f° from level%s\n", r.tiltDeg, r.still ? "" : " (still moving)");
}

bool imuUnusedImpact(Impact& impact) {
  const ImuReading r = imuNow();
  if (!r.present || r.impacts == usedImpacts) return false;
  const uint32_t age = millis() - r.lastImpactMs;
  if (age > IMU_FELT_WINDOW_MS) return false;
  impact = {r.lastImpactPeakG, age};
  return true;
}

void imuUseImpacts() { usedImpacts = imuNow().impacts; }

bool imuSaveLevel(String& why) {
  const ImuReading r = imuNow();
  if (!r.present) {
    why = "no IMU found";
    return false;
  }
  if (servoAngle != settings::homeAngle) {
    why = "the plate isn't home: type \"servo " + String(settings::homeAngle.load()) + "\" first";
    return false;
  }
  if (!r.still) {
    why = "the plate is moving: let it settle and try again";
    return false;
  }
  settings::saveImuLevel(r.gravityG);
  portENTER_CRITICAL(&lock);
  level = r.gravityG;
  haveLevel = true;
  portEXIT_CRITICAL(&lock);
  return true;
}
