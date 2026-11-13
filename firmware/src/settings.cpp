#include "settings.h"

#include <Preferences.h>

#include "config.h"

const char* modeName(Mode mode) { return mode == Mode::Llm ? "llm" : "yolo"; }

namespace settings {

String wifiSsid;
String wifiPass;
String serverUrl;
Mode mode = Mode::Yolo;
String llmModel = LLM_DEFAULT_MODEL;
int jpegQuality = DEFAULT_JPEG_QUALITY;
float wifiTxDbm = DEFAULT_WIFI_TX_DBM;
imu::Vec3 imuLevel;
bool haveImuLevel = false;

std::atomic<float> minConfidence{DEFAULT_MIN_CONFIDENCE};
std::atomic<int> homeAngle{DEFAULT_ANGLE_HOME};
std::atomic<int> servoSpeed{DEFAULT_SERVO_SPEED_DPS};
std::atomic<bool> autoScan{true};
std::atomic<bool> imuOn{true};

Destination destinations[3] = {
    {"paper", "a_paper", DEFAULT_ANGLE_PAPER, "1", 0},
    {"plastic_bottles", "a_bottles", DEFAULT_ANGLE_BOTTLES, "2", 0},
    {"other", "a_other", DEFAULT_ANGLE_OTHER, "3 and 4", 0},
};

namespace {

Preferences prefs;
ScanSettings scanSettings;
SemaphoreHandle_t scanSettingsMutex = nullptr;

void publishScanSettings() {
  xSemaphoreTake(scanSettingsMutex, portMAX_DELAY);
  scanSettings = {mode, serverUrl, llmModel};
  xSemaphoreGive(scanSettingsMutex);
}

String savedString(const char* key, const char* fallback) {
  return prefs.isKey(key) ? prefs.getString(key, fallback) : String(fallback);
}

}  // namespace

Destination& destinationFor(routing::Stream stream) { return destinations[static_cast<int>(stream)]; }

Destination* findDestination(const String& stream) {
  for (auto& d : destinations) {
    if (stream == d.stream) return &d;
  }
  return nullptr;
}

void load() {
  prefs.begin("awarebin", false);
  wifiSsid = savedString("ssid", LOCAL_WIFI_SSID);
  wifiPass = savedString("pass", LOCAL_WIFI_PASS);
  serverUrl = savedString("server", LOCAL_SERVER_URL);
  minConfidence = prefs.isKey("min_conf") ? prefs.getFloat("min_conf", DEFAULT_MIN_CONFIDENCE) : DEFAULT_MIN_CONFIDENCE;
  homeAngle = prefs.isKey("a_home") ? prefs.getInt("a_home", DEFAULT_ANGLE_HOME) : DEFAULT_ANGLE_HOME;
  for (auto& d : destinations) d.angle = prefs.isKey(d.prefKey) ? prefs.getInt(d.prefKey, d.defaultAngle) : d.defaultAngle;
  servoSpeed = prefs.isKey("servo_dps") ? prefs.getInt("servo_dps", DEFAULT_SERVO_SPEED_DPS) : DEFAULT_SERVO_SPEED_DPS;
  jpegQuality = prefs.isKey("jpeg_q") ? prefs.getInt("jpeg_q", DEFAULT_JPEG_QUALITY) : DEFAULT_JPEG_QUALITY;
  wifiTxDbm = prefs.isKey("tx_dbm") ? prefs.getFloat("tx_dbm", DEFAULT_WIFI_TX_DBM) : DEFAULT_WIFI_TX_DBM;
  mode = savedString("mode", "yolo") == "llm" ? Mode::Llm : Mode::Yolo;
  llmModel = savedString("llm_model", LLM_DEFAULT_MODEL);
  imuOn = prefs.isKey("imu_on") ? prefs.getBool("imu_on", true) : true;
  haveImuLevel = prefs.isKey("imu_level") && prefs.getBytes("imu_level", &imuLevel, sizeof(imuLevel)) == sizeof(imuLevel);
  scanSettingsMutex = xSemaphoreCreateMutex();
  publishScanSettings();
}

ScanSettings forScan() {
  xSemaphoreTake(scanSettingsMutex, portMAX_DELAY);
  ScanSettings copy = scanSettings;
  xSemaphoreGive(scanSettingsMutex);
  return copy;
}

void saveWifiSsid(const String& ssid) {
  wifiSsid = ssid;
  prefs.putString("ssid", ssid);
}

void saveWifiPass(const String& pass) {
  wifiPass = pass;
  prefs.putString("pass", pass);
}

void saveServerUrl(const String& url) {
  serverUrl = url;
  prefs.putString("server", url);
  publishScanSettings();
}

void saveMode(Mode value) {
  mode = value;
  prefs.putString("mode", modeName(value));
  publishScanSettings();
}

void saveLlmModel(const String& model) {
  llmModel = model;
  prefs.putString("llm_model", model);
  publishScanSettings();
}

void saveMinConfidence(float value) {
  minConfidence = value;
  prefs.putFloat("min_conf", value);
}

void saveHomeAngle(int angle) {
  homeAngle = angle;
  prefs.putInt("a_home", angle);
}

void saveAngle(Destination& destination, int angle) {
  destination.angle = angle;
  prefs.putInt(destination.prefKey, angle);
}

void saveServoSpeed(int degreesPerSecond) {
  servoSpeed = degreesPerSecond;
  prefs.putInt("servo_dps", degreesPerSecond);
}

void saveJpegQuality(int quality) {
  jpegQuality = quality;
  prefs.putInt("jpeg_q", quality);
}

void saveWifiTxDbm(float dbm) {
  wifiTxDbm = dbm;
  prefs.putFloat("tx_dbm", dbm);
}

void saveImuOn(bool on) {
  imuOn = on;
  prefs.putBool("imu_on", on);
}

void saveImuLevel(imu::Vec3 level) {
  imuLevel = level;
  haveImuLevel = true;
  prefs.putBytes("imu_level", &level, sizeof(level));
}

}  // namespace settings
