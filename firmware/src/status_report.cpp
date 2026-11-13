#include "status_report.h"

#include <Arduino.h>
#include <WiFi.h>

#include <algorithm>
#include <cstdarg>
#include <iterator>
#include <vector>

#include "camera.h"
#include "config.h"
#include "console.h"
#include "esp_mac.h"
#include "esp_timer.h"
#include "imu.h"
#include "llm.h"
#include "plate_watch.h"
#include "server_link.h"
#include "servo.h"
#include "settings.h"
#include "wifi_join.h"
#include "worker.h"

namespace {

String formatText(const char* text, ...) __attribute__((format(printf, 1, 2)));
String formatText(const char* text, ...) {
  char buffer[192];
  va_list args;
  va_start(args, text);
  vsnprintf(buffer, sizeof(buffer), text, args);
  va_end(args);
  return buffer;
}

String paint(const char* color, const String& text) { return String("\x1b[") + color + "m" + text + "\x1b[0m"; }

String macAddress() {
  uint8_t mac[6] = {};
  esp_read_mac(mac, ESP_MAC_WIFI_STA);
  return formatText("%02x:%02x:%02x:%02x:%02x:%02x", mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
}

String uptime() {
  const uint32_t minutes = static_cast<uint32_t>(esp_timer_get_time() / 60000000ULL);
  const uint32_t days = minutes / 1440, hours = minutes / 60 % 24, mins = minutes % 60;
  String text;
  auto add = [&text](uint32_t n, const char* unit) {
    if (n == 0) return;
    if (!text.isEmpty()) text += ", ";
    text += String(n) + " " + unit + (n == 1 ? "" : "s");
  };
  add(days, "day");
  add(hours, "hour");
  add(mins, "min");
  if (text.isEmpty()) add(static_cast<uint32_t>(esp_timer_get_time() / 1000000ULL), "sec");
  return text;
}

String signalText(int rssi) {
  const int bars = rssi >= -55 ? 4 : rssi >= -65 ? 3 : rssi >= -75 ? 2 : 1;
  const char* const words[] = {"", "very weak", "weak", "good", "strong"};
  const char* const glyphs[] = {"▂", "▄", "▆", "█"};
  String text = String("\x1b[") + (bars >= 3 ? "32" : bars == 2 ? "33" : "31") + "m";
  for (int i = 0; i < 4; ++i) {
    if (i == bars) text += "\x1b[90m";
    text += glyphs[i];
  }
  return text + "\x1b[0m " + String(rssi) + " dBm, " + words[bars];
}

// The bin, in letters like neofetch's logos, one color per row.
const struct {
  const char* color;
  const char* text;
} kArt[] = {
    {"1;32", "            .;odxdo;."},
    {"1;32", "           kWd'   'dWk"},
    {"92", " .,;:clloddxxxxxxxxxxxddollc:;,."},
    {"92", " xMMMMMMMMMMMMMMMMMMMMMMMMMMMMMx"},
    {"92", " ':ccccccccccccccccccccccccccc:'"},
    {"32", "  kM    dMo    MMM    oMd    Mk"},
    {"32", "  kM    dMo    MMM    oMd    Mk"},
    {"32", "  kM    dMo    MMM    oMd    Mk"},
    {"36", "   kM   dMo    MMM    oMd   Mk"},
    {"36", "   kM   dMo    MMM    oMd   Mk"},
    {"36", "   kM   dMo    MMM    oMd   Mk"},
    {"96", "    kM  dMo    MMM    oMd  Mk"},
    {"96", "    kM  dMo    MMM    oMd  Mk"},
    {"96", "    kM  dMo    MMM    oMd  Mk"},
    {"34", "     kM dMo    MMM    oMd Mk"},
    {"94", "     'xOOOOOOOOOOOOOOOOOOOx'"},
};
constexpr size_t kArtWidth = 32;

// The IMU in one line, for "status".
String imuText() {
  if (!imuPresent()) return paint("90", formatText("none on GPIO %d (SDA) and %d (SCL)", IMU_PIN_SDA, IMU_PIN_SCL));
  if (!settings::imuOn) return imuChipText() + ", " + paint("33", "off");
  const ImuReading r = imuNow();
  const String tilt = formatText("tilt %.1f°", r.tiltDeg);
  return imuChipText() + ", " + (r.tiltDeg > IMU_LEVEL_TOLERANCE_DEG ? paint("31", tilt) : tilt) +
         (settings::haveImuLevel ? "" : " (from flat: no level saved)") + (r.still ? ", still" : ", moving");
}

}  // namespace

void printImu() {
  if (!imuPresent()) {
    say("IMU: none on GPIO %d (SDA) and %d (SCL). The bin runs without it and looks for one every %u s.\n",
        IMU_PIN_SDA, IMU_PIN_SCL, static_cast<unsigned>(IMU_RETRY_MS / 1000));
    return;
  }
  const ImuReading r = imuNow();
  const float g = imu::length(r.gravityG);
  String impacts = "none yet";
  if (r.impacts) {
    impacts = formatText("%u, the last %.2f g, %.0f s ago", static_cast<unsigned>(r.impacts), r.lastImpactPeakG,
                         (millis() - r.lastImpactMs) / 1000.0);
  }
  ConsoleLock lock;
  Serial.printf("IMU: %s on GPIO %d (SDA) and %d (SCL), %s\n", imuChipText().c_str(), IMU_PIN_SDA, IMU_PIN_SCL,
                settings::imuOn ? "in use" : "off (\"imu on\")");
  Serial.printf("Tilt: %.1f° %s (level within %.1f°)\n", r.tiltDeg,
                settings::haveImuLevel ? "from the saved level" : "from flat; no level saved (\"imu level\")",
                IMU_LEVEL_TOLERANCE_DEG);
  if (r.still) {
    Serial.printf("Plate: still for %.1f s, shake %.3f g\n", r.stillForMs / 1000.0, r.shakeG);
  } else {
    Serial.printf("Plate: moving, shake %.3f g\n", r.shakeG);
  }
  Serial.printf("Gravity: x %.3f, y %.3f, z %.3f g (%.2f g%s)\n", r.gravityG.x, r.gravityG.y, r.gravityG.z, g,
                r.still && (g < 0.9f || g > 1.1f) ? ": 1 g expected at rest, so the chip's range may be off" : "");
  Serial.printf("Rotation: %.1f°/s, temperature %.1f °C\n", r.rotationDps, r.temperatureC);
  Serial.printf("Impacts: %s (one counts above %.2f g)\n", impacts.c_str(), IMU_IMPACT_G);
}

void printStatus() {
  const bool llmMode = settings::mode == Mode::Llm;
  const String deviceId = macAddress();
  std::vector<String> info;
  auto add = [&info](const char* key, const String& value) { info.push_back(paint("1;33", key) + ": " + value); };
  info.push_back(paint("1;32", "aware-bin") + "@" + paint("1;32", deviceId));
  String dashes;
  for (size_t i = 0; i < strlen("aware-bin@") + deviceId.length(); ++i) dashes += '-';
  info.push_back(dashes);

  const uint16_t rev = ESP.getChipRevision();
  add("Firmware", String(FIRMWARE_VERSION) + ", routing-v1");
  add("Board", formatText("%s rev v%u.%u, %u MHz, %u MB flash", ESP.getChipModel(), rev / 100, rev % 100,
                          static_cast<unsigned>(ESP.getCpuFreqMHz()), static_cast<unsigned>(ESP.getFlashChipSize() >> 20)));
  add("Uptime", uptime());
#ifdef AWARE_SIMULATOR
  add("Camera", cameraReady ? String("simulator photos (no live camera)") : paint("31", "no simulator photos"));
  add("Auto scan", settings::autoScan ? String("on an MPU-6050 impact (no camera to watch)") : paint("33", "off"));
#else
  add("Camera", cameraReady ? formatText("%s, 640x480, JPEG quality %d", cameraModel(), settings::jpegQuality)
                            : paint("31", "NOT ready"));
  add("Auto scan", settings::autoScan ? String("on") : paint("33", "off"));
#endif
  add("IMU", imuText());
  const Activity now = workerActivity();
  const unsigned waiting = waitingJobs();
  add("Bin", (now == Activity::Free ? paint("32", "free") : paint("33", activityText(now))) +
                 (waiting ? formatText(", %u command%s waiting", waiting, waiting == 1 ? "" : "s") : String()));
  if (kLiveCamera && liveWanted()) add("Live view", paint("32", "on") + ", to scripts/viewer.py");
  add("Servo", formatText("at %d°, %d°/s", servoAngle.load(), settings::servoSpeed.load()));
  String angles = formatText("home %d", settings::homeAngle.load());
  for (const auto& d : settings::destinations) angles += formatText(", %s %d", d.stream, d.angle.load());
  add("Angles", angles);
  add("Routing", formatText("min confidence %.2f%s", settings::minConfidence.load(), llmMode ? " (yolo mode only)" : ""));
  add("Mode", llmMode ? "llm, " + settings::llmModel + ", reasoning " LLM_REASONING_EFFORT ", image detail " LLM_IMAGE_DETAIL
                      : String("yolo, on the detection server"));
  add("ChatGPT", llmSignedIn() ? llmSignInText() : paint(llmMode ? "31" : "90", llmSignInText()));
  if (WiFi.status() == WL_CONNECTED) {
    add("Wi-Fi", "\"" + settings::wifiSsid + "\" " + signalText(WiFi.RSSI()));
    add("IP", WiFi.localIP().toString() + formatText(", transmit power %.1f dBm", txPowerNow()));
  } else {
    add("Wi-Fi", "\"" + settings::wifiSsid + "\" " + (wifiJoining() ? paint("33", "joining") : paint("31", "not connected")));
  }
  String server = llmMode ? String(LLM_URL) : settings::serverUrl;
  server.replace("https://", "");
  server.replace("http://", "");
  add("Server", server.isEmpty() ? paint("31", "not set")
                                 : server + ", " + (linkIsOpen() ? paint("32", "connected") : paint("31", "not connected")));
  const uint32_t heapTotal = ESP.getHeapSize(), heapUsed = heapTotal - ESP.getFreeHeap();
  const uint32_t psramTotal = ESP.getPsramSize(), psramUsed = psramTotal - ESP.getFreePsram();
  add("Memory", formatText("%uKiB / %uKiB, PSRAM %.1fMiB / %.1fMiB", static_cast<unsigned>(heapUsed >> 10),
                           static_cast<unsigned>(heapTotal >> 10), psramUsed / 1048576.0, psramTotal / 1048576.0));
  info.push_back("");
  String dark, bright;
  for (int c = 0; c < 8; ++c) {
    dark += formatText("\x1b[4%dm   ", c);
    bright += formatText("\x1b[10%dm   ", c);
  }
  info.push_back(dark + "\x1b[0m");
  info.push_back(bright + "\x1b[0m");

  ConsoleLock lock;
  const size_t rows = std::max(info.size(), std::size(kArt));
  for (size_t i = 0; i < rows; ++i) {
    String row;
    if (i < std::size(kArt)) {
      row = paint(kArt[i].color, kArt[i].text);
      for (size_t pad = strlen(kArt[i].text); pad < kArtWidth; ++pad) row += ' ';
    } else {
      for (size_t pad = 0; pad < kArtWidth; ++pad) row += ' ';
    }
    row += "   ";
    if (i < info.size()) row += info[i];
    Serial.println(row);
  }
}
