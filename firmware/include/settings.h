// The bin's settings. The command that changes one also saves it on the board
// (NVS, namespace "awarebin"); a setting that was never saved takes its
// default from config.h (or local_settings.h).
//
// The ones marked "shared" are changed by the console and read by the worker
// while it runs. The rest belong to the console; a scan gets the ones it
// needs through forScan().
#pragma once

#include <Arduino.h>

#include <atomic>

#include "imu_math.h"
#include "routing.h"

// Who names the items on the plate: the detection server's YOLO model, or an
// LLM that the board asks itself (llm.h).
enum class Mode : uint8_t { Yolo, Llm };
const char* modeName(Mode mode);

// Where the servo turns for one routing-v1 stream.
struct Destination {
  const char* stream;      // routing-v1 stream
  const char* prefKey;     // where its angle is saved
  int defaultAngle;
  const char* liners;      // routing-v1 liners, for the log
  std::atomic<int> angle;  // shared
};

// What a scan uses: the console publishes a copy after each change, and each
// scan takes one at its start, so a scan never mixes two modes.
struct ScanSettings {
  Mode mode = Mode::Yolo;
  String serverUrl;
  String model;
};

namespace settings {

// Console only.
extern String wifiSsid;
extern String wifiPass;
extern String serverUrl;
extern Mode mode;
extern String llmModel;
extern int jpegQuality;
extern float wifiTxDbm;
extern imu::Vec3 imuLevel;  // the way gravity points with the plate level ("imu level")
extern bool haveImuLevel;

// Shared.
extern std::atomic<float> minConfidence;
extern std::atomic<int> homeAngle;
extern std::atomic<int> servoSpeed;
extern std::atomic<bool> autoScan;   // not saved: "auto off" lasts until the next start
extern std::atomic<bool> imuOn;      // "imu off" ignores the IMU
extern Destination destinations[3];  // same order as routing::Stream

Destination& destinationFor(routing::Stream stream);
Destination* findDestination(const String& stream);  // nullptr for a name that isn't a stream

// Call once in setup(), before anything reads them.
void load();

// A copy of what the next scan uses.
ScanSettings forScan();

// Each one changes a setting and saves it. Console only.
void saveWifiSsid(const String& ssid);
void saveWifiPass(const String& pass);
void saveServerUrl(const String& url);
void saveMode(Mode value);
void saveLlmModel(const String& model);
void saveMinConfidence(float value);
void saveHomeAngle(int angle);
void saveAngle(Destination& destination, int angle);
void saveServoSpeed(int degreesPerSecond);
void saveJpegQuality(int quality);
void saveWifiTxDbm(float dbm);
void saveImuOn(bool on);
void saveImuLevel(imu::Vec3 level);

}  // namespace settings
