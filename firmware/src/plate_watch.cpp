#include "plate_watch.h"

#include <Arduino.h>

#include <atomic>

#include "camera.h"
#include "config.h"
#include "console.h"
#include "imu.h"
#include "presence.h"
#include "scan.h"
#include "servo.h"
#include "settings.h"
#include "worker.h"

namespace {

// The viewer's heartbeat keeps the live view on until this time.
std::atomic<uint32_t> liveUntil{0};

// Share of the pixels (0-1) that differ by more than WATCH_PIXEL_DIFF.
float changedShare(const uint8_t* a, const uint8_t* b) {
  int changed = 0;
  for (int i = 0; i < THUMB_PIXELS; ++i) changed += abs(a[i] - b[i]) > WATCH_PIXEL_DIFF;
  return static_cast<float>(changed) / THUMB_PIXELS;
}

constexpr presence::Rules kRules = {WATCH_ITEM_SHARE, WATCH_FELT_SHARE, WATCH_LIGHT_SHARE, IMU_BUMP_AFTER_MS};

struct Watch {
  uint8_t empty[THUMB_PIXELS];
  uint8_t last[THUMB_PIXELS];
  uint8_t now[THUMB_PIXELS];
  bool haveEmpty = false;
  int stillChecks = 0;
} watch;

// Checks one frame; returns true when an item has landed and stopped moving.
bool itemLanded(const Photo& frame) {
  if (!cameraThumbnail(frame, watch.now)) return false;
  watch.stillChecks = changedShare(watch.now, watch.last) < WATCH_STILL_SHARE ? watch.stillChecks + 1 : 0;
  memcpy(watch.last, watch.now, THUMB_PIXELS);
  if (watch.stillChecks < WATCH_STILL_CHECKS) return false;

  if (!watch.haveEmpty) {
    say("[watch] plate empty, watching\n");
    memcpy(watch.empty, watch.now, THUMB_PIXELS);
    watch.haveEmpty = true;
    return false;
  }
  const float changed = changedShare(watch.now, watch.empty);
  const bool imuUsed = imuInUse();
  Impact impact{};
  const bool felt = imuUsed && imuUnusedImpact(impact);
  switch (presence::judge(changed, imuUsed, felt, impact.ageMs, kRules)) {
    case presence::Verdict::Empty:
      memcpy(watch.empty, watch.now, THUMB_PIXELS);  // also follows slow changes in the light
      return false;
    case presence::Verdict::Lighting:
      say("[watch] %.0f%% of the plate changed but nothing landed on it (the light?): watching the new view\n",
          changed * 100);
      memcpy(watch.empty, watch.now, THUMB_PIXELS);
      return false;
    case presence::Verdict::Bump:
      say("[watch] felt a bump (%.2f g) but the plate looks the same: not scanning\n", impact.peakG);
      imuUseImpacts();
      memcpy(watch.empty, watch.now, THUMB_PIXELS);
      return false;
    case presence::Verdict::Scan:
      break;
  }
  if (felt) {
    say("[watch] felt an impact (%.2f g) and %.1f%% of the plate changed: scanning\n", impact.peakG, changed * 100);
  } else {
    say("[watch] %.1f%% of the plate changed and nothing moves: scanning%s\n", changed * 100,
        imuUsed ? " (nothing felt: a light item?)" : "");
  }
  // Whatever is still on the plate after the scan counts as empty.
  watch.haveEmpty = false;
  watch.stillChecks = 0;
  return true;
}

// The simulator has no live camera, so an impact alone (a change to the
// MPU-6050's readings in the diagram) stands for an item landing.
bool feltInSimulator() {
  Impact impact{};
  if (!settings::autoScan || servoAngle != settings::homeAngle || !imuInUse() || !imuUnusedImpact(impact)) {
    return false;
  }
  if (impact.ageMs < WATCH_STILL_CHECKS * WATCH_INTERVAL_MS) return false;  // as the camera would wait
  say("[watch] felt an impact (%.2f g), and the simulator has no camera to look: scanning\n", impact.peakG);
  return true;
}

}  // namespace

void liveKeepOn() { liveUntil = millis() + LIVE_HOLD_MS; }

void liveStop() { liveUntil = millis(); }

bool liveWanted() { return static_cast<int32_t>(liveUntil.load() - millis()) > 0; }

bool lookAtPlate() {
  static uint32_t watchedAt = 0;
  if (!kLiveCamera) return feltInSimulator();
  const bool live = liveWanted();
  // The watch needs the plate at home ("servo" can leave it tipped), and
  // checks every WATCH_INTERVAL_MS even while the live view runs faster.
  const bool watching =
      settings::autoScan && servoAngle == settings::homeAngle && millis() - watchedAt >= WATCH_INTERVAL_MS;
  if (!cameraReady || (!live && !watching)) return false;
  if (watching) watchedAt = millis();
  HeldPhoto frame;  // goes back on return, before the scan takes its own photo
  if (!cameraTake(frame.photo)) return false;
  const bool landed = watching && itemLanded(frame.photo);
  if (live) sendPhoto(frame.photo, "LIVE");
  return landed;
}
