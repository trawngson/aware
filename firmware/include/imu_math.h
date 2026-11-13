// The IMU's arithmetic (imu.h) as plain C++, so it runs on the board and in
// the native unit tests: decoding the MPU-6050's registers, the plate's tilt,
// and the tracker that tells a resting plate from a shaken one and spots the
// jolt of an item landing.
#pragma once

#include <cmath>
#include <cstdint>

namespace imu {

struct Vec3 {
  float x = 0, y = 0, z = 0;
};

inline Vec3 operator-(Vec3 a, Vec3 b) { return {a.x - b.x, a.y - b.y, a.z - b.z}; }
inline float dot(Vec3 a, Vec3 b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
inline float length(Vec3 v) { return std::sqrt(dot(v, v)); }

constexpr float kDegreesPerRadian = 57.29578f;

// Degrees between the way gravity points now and the way it pointed when the
// plate was level ("imu level"). With no saved level it assumes the chip lies
// flat on the plate, either side up, so only the Z axis matters.
inline float tiltDegrees(Vec3 gravity, Vec3 level, bool haveLevel) {
  const float g = length(gravity);
  if (g < 0.1f) return 0;  // free fall or no reading: no direction to measure
  float cosine;
  if (haveLevel) {
    const float l = length(level);
    if (l < 0.1f) return 0;
    cosine = dot(gravity, level) / (g * l);
  } else {
    cosine = std::fabs(gravity.z) / g;
  }
  if (cosine > 1) cosine = 1;
  if (cosine < -1) cosine = -1;
  return std::acos(cosine) * kDegreesPerRadian;
}

// The 14 bytes from ACCEL_XOUT_H (0x3B) on: accelerometer, temperature,
// gyro, each a big-endian int16.
struct Sample {
  Vec3 accelG;
  Vec3 gyroDps;
  float temperatureC = 0;
};

inline int16_t bigEndian(const uint8_t* p) { return static_cast<int16_t>((p[0] << 8) | p[1]); }

inline Sample decode(const uint8_t raw[14], float accelLsbPerG, float gyroLsbPerDps) {
  Sample s;
  s.accelG = {bigEndian(raw) / accelLsbPerG, bigEndian(raw + 2) / accelLsbPerG, bigEndian(raw + 4) / accelLsbPerG};
  s.temperatureC = bigEndian(raw + 6) / 340.0f + 36.53f;
  s.gyroDps = {bigEndian(raw + 8) / gyroLsbPerDps, bigEndian(raw + 10) / gyroLsbPerDps,
               bigEndian(raw + 12) / gyroLsbPerDps};
  return s;
}

struct Tuning {
  float sampleHz = 200;
  float gravityTauS = 0.1f;   // smoothing for the tilt reading
  float baselineTauS = 0.5f;  // the slow average that a jolt stands out from
  float stillG = 0.03f;       // shake below this counts as still
  float impactG = 0.08f;      // shake above this is an impact...
  float rearmG = 0.04f;       // ...and the next one counts once shake falls below this
  uint32_t impactGapMs = 300; // bounces closer together than this are one impact
  float gyroBiasTauS = 2;     // the gyro's zero, learned while the plate is still
};

// Fed every sample. Shake is how far the acceleration is from its slow
// average, so gravity (whatever the tilt) reads 0 and a jolt or a wobble
// stands out. An impact is shake rising past impactG; it counts once, and
// the next one only after shake has fallen below rearmG and impactGapMs has
// passed, so one landing and its bounces count once.
class Tracker {
 public:
  explicit Tracker(const Tuning& tuning = Tuning())
      : tuning_(tuning),
        gravityAlpha_(alphaFor(tuning.gravityTauS)),
        baselineAlpha_(alphaFor(tuning.baselineTauS)),
        biasAlpha_(alphaFor(tuning.gyroBiasTauS)) {}

  // countImpacts false (the servo is moving) still follows the plate but
  // counts no impact. True when this sample starts a new impact.
  bool update(const Sample& s, uint32_t nowMs, bool countImpacts) {
    if (!started_) {
      started_ = true;
      gravity_ = baseline_ = s.accelG;
      gyroBias_ = s.gyroDps;
      stillSinceMs_ = nowMs;
    }
    follow(gravity_, s.accelG, gravityAlpha_);
    follow(baseline_, s.accelG, baselineAlpha_);
    shakeG_ = length(s.accelG - baseline_);

    const bool stillNow = shakeG_ < tuning_.stillG;
    if (stillNow && !still_) stillSinceMs_ = nowMs;
    still_ = stillNow;
    if (still_) follow(gyroBias_, s.gyroDps, biasAlpha_);
    rotationDps_ = length(s.gyroDps - gyroBias_);

    bool impact = false;
    if (armed_) {
      if (shakeG_ > tuning_.impactG) {
        armed_ = false;
        if (countImpacts && (impacts_ == 0 || nowMs - lastImpactMs_ >= tuning_.impactGapMs)) {
          impact = true;
          ++impacts_;
          lastImpactMs_ = nowMs;
          peakG_ = shakeG_;
          inImpact_ = true;
        }
      }
    } else {
      if (inImpact_ && shakeG_ > peakG_) peakG_ = shakeG_;
      if (shakeG_ < tuning_.rearmG) {
        armed_ = true;
        inImpact_ = false;
      }
    }
    return impact;
  }

  Vec3 gravity() const { return gravity_; }
  float shakeG() const { return shakeG_; }
  float rotationDps() const { return rotationDps_; }
  bool still() const { return still_; }
  uint32_t stillForMs(uint32_t nowMs) const { return still_ ? nowMs - stillSinceMs_ : 0; }
  uint32_t impacts() const { return impacts_; }
  uint32_t lastImpactMs() const { return lastImpactMs_; }
  float lastImpactPeakG() const { return peakG_; }

 private:
  float alphaFor(float tauS) const { return 1 - std::exp(-1 / (tuning_.sampleHz * tauS)); }
  static void follow(Vec3& average, Vec3 value, float alpha) {
    average.x += alpha * (value.x - average.x);
    average.y += alpha * (value.y - average.y);
    average.z += alpha * (value.z - average.z);
  }

  Tuning tuning_;
  float gravityAlpha_, baselineAlpha_, biasAlpha_;
  bool started_ = false;
  Vec3 gravity_, baseline_, gyroBias_;
  float shakeG_ = 0, rotationDps_ = 0;
  bool still_ = false;
  uint32_t stillSinceMs_ = 0;
  bool armed_ = true, inImpact_ = false;
  uint32_t impacts_ = 0, lastImpactMs_ = 0;
  float peakG_ = 0;
};

}  // namespace imu
