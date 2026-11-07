// AWARE bin MVP: one ESP32-S3 camera board and one servo.
//
// Press the BOOT button (or type "scan"): the board photographs the plate,
// sends the JPEG to the detection server, routes the detections with the
// routing-v1 rules, and turns the servo to that stream's angle. It holds
// there, then returns home. On any failure it holds: the servo stays home.
//
// Three tasks share the work, so typed commands are read at all times, even
// during a scan:
// - the console (Arduino's loop) runs the prompt (console.cpp), the BOOT
//   button and Wi-Fi changes, and at once every command that only reads or
//   saves settings;
// - the worker owns the camera, the servo and the LED. It watches the plate,
//   scans, and runs "scan", "snap", "servo" and "angle" in the order they
//   came;
// - the link task keeps the server connection open (server_link.cpp).

#include <Arduino.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <WiFi.h>

#include <algorithm>
#include <atomic>
#include <cstdarg>
#include <iterator>

#include "camera.h"
#include "config.h"
#include "console.h"
#include "esp_mac.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "mbedtls/base64.h"
#include "routing.h"
#include "server_link.h"
#include "status_led.h"

namespace {

// Settings marked "shared" are saved by the console and read by the worker.
struct Destination {
  const char* stream;   // routing-v1 stream
  const char* prefKey;  // where its angle is saved
  int defaultAngle;
  const char* liners;   // routing-v1 liners, for the log
  std::atomic<int> angle;  // shared
};

Destination destinations[] = {
    {"paper", "a_paper", DEFAULT_ANGLE_PAPER, "1", 0},
    {"plastic_bottles", "a_bottles", DEFAULT_ANGLE_BOTTLES, "2", 0},
    {"other", "a_other", DEFAULT_ANGLE_OTHER, "3 and 4", 0},
};
// Same order as routing::Stream.
Destination& destinationFor(routing::Stream stream) { return destinations[static_cast<int>(stream)]; }

// Console only.
Preferences prefs;
String wifiSsid;
String wifiPass;
String serverUrl;
String deviceId;
int jpegQuality = DEFAULT_JPEG_QUALITY;
float wifiTxDbm = DEFAULT_WIFI_TX_DBM;
bool joining = false;  // "connect" started joining Wi-Fi
uint32_t joinStartedAt = 0;
bool lastCommandOk = true;  // the prompt's arrow turns red after a failed command

// Shared.
std::atomic<float> minConfidence{DEFAULT_MIN_CONFIDENCE};
std::atomic<int> homeAngle{DEFAULT_ANGLE_HOME};
std::atomic<int> servoSpeed{DEFAULT_SERVO_SPEED_DPS};
std::atomic<bool> autoScan{true};  // watchPlate; "auto off" stops it until the next start

// Worker only, except that the console reads them for "status" and the prompt.
std::atomic<int> servoAngle{-1};
std::atomic<bool> cameraReady{false};  // set in setup(), and by "camera on|off"

// ---- Worker jobs -----------------------------------------------------------

enum class Job : uint8_t { Scan, Snap, Servo, ShowAngle, CameraOff, CameraOn };

struct Work {
  Job job;
  int angle;  // Servo and ShowAngle
};

QueueHandle_t workQueue = nullptr;

// What the worker is doing, for the console's messages and the prompt.
enum class Activity : uint8_t { Free, Scanning, Photo, Servo, Angle };
const char* const kActivityText[] = {"free", "scanning", "taking a photo", "turning the servo", "showing an angle"};
std::atomic<Activity> activity{Activity::Free};
// A scan is waiting in the queue; another "scan" or BOOT press is skipped.
std::atomic<bool> scanQueued{false};

struct Busy {
  explicit Busy(Activity what) { activity = what; }
  ~Busy() { activity = Activity::Free; }
};

const char* activityText() { return kActivityText[static_cast<int>(activity.load())]; }

unsigned waitingJobs() { return workQueue ? uxQueueMessagesWaiting(workQueue) : 0; }

Destination* findDestination(const String& name) {
  for (auto& d : destinations) {
    if (name == d.stream) return &d;
  }
  return nullptr;
}

String savedString(const char* key, const char* fallback) {
  return prefs.isKey(key) ? prefs.getString(key, fallback) : String(fallback);
}

void loadSettings() {
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
}

String formatText(const char* text, ...) __attribute__((format(printf, 1, 2)));
String formatText(const char* text, ...) {
  char buffer[192];
  va_list args;
  va_start(args, text);
  vsnprintf(buffer, sizeof(buffer), text, args);
  va_end(args);
  return buffer;
}

String macAddress() {
  uint8_t mac[6] = {};
  esp_read_mac(mac, ESP_MAC_WIFI_STA);
  return formatText("%02x:%02x:%02x:%02x:%02x:%02x", mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
}

// ---- Servo (worker) --------------------------------------------------------

uint32_t dutyFor(int angle) {
  const uint32_t pulseUs =
      SERVO_MIN_PULSE_US + (SERVO_MAX_PULSE_US - SERVO_MIN_PULSE_US) * static_cast<uint32_t>(angle) / 180;
  const uint32_t maxDuty = (1u << SERVO_LEDC_BITS) - 1;
  return pulseUs * maxDuty / SERVO_PERIOD_US;
}

void writeServo(int angle) {
  ledcWrite(SERVO_PIN, dutyFor(angle));
  servoAngle = angle;
}

// Ramps one degree at a time at servoSpeed degrees a second; 0 jumps
// straight there and lets the servo move at its own top speed.
void moveServo(int target) {
  target = constrain(target, 0, 180);
  const int from = servoAngle;
  const int speed = servoSpeed;  // once: "speed" may change it mid-move
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
  delay(DWELL_MS);
  moveServo(homeAngle);
}

// ---- Routing ---------------------------------------------------------------

String describe(const routing::Decision& d, float confidenceLimit) {
  switch (d.reason) {
    case routing::Reason::OneStream:
      return String("every item goes to ") + routing::streamName(d.stream);
    case routing::Reason::NothingDetected:
      return "nothing detected";
    case routing::Reason::LowConfidence:
      return String(d.label) + " is below confidence " + String(confidenceLimit, 2);
    case routing::Reason::UnknownLabel:
      return String("\"") + d.label + "\" is not a bin class";
    case routing::Reason::Mixed:
      return "the items belong in more than one bin";
  }
  return "";
}

// ---- Scan (worker) ---------------------------------------------------------

void printPhoto(const char* tag, const Photo& photo) {
  say("%s photo %ux%u, %u KB%s%s%s\n", tag, photo.width, photo.height, static_cast<unsigned>(photo.length / 1024),
      photo.name ? " (" : "", photo.name ? photo.name : "", photo.name ? ")" : "");
}

void hold(const String& why) {
  ledShow(LedStage::Error);
  say("[hold] %s. The servo stays home.\n", why.c_str());
}

void printTiming(uint32_t photoMs, const LinkTiming& t, uint32_t decideMs, uint32_t servoMs, uint32_t totalMs) {
  say("[time] photo %u | connect %u%s | send %u | wait %u | read %u | decide %u | servo %u | total %u ms\n",
      static_cast<unsigned>(photoMs), static_cast<unsigned>(t.connectMs), t.reused ? " (kept open)" : " (new connection)",
      static_cast<unsigned>(t.sendMs), static_cast<unsigned>(t.waitMs), static_cast<unsigned>(t.readMs),
      static_cast<unsigned>(decideMs), static_cast<unsigned>(servoMs), static_cast<unsigned>(totalMs));
}

// Sends the photo to scripts/viewer.py on the Mac as base64 text, between the
// control bytes STX and ETX, with "-----BEGIN JPEG <bytes>-----" and
// "-----END JPEG-----" inside ("JPEG" for a scan or snap, "LIVE" for a frame
// of the live view). The monitor's aware_feed filter takes everything from STX
// to ETX out of the terminal, wherever it comes, so the prompt line is left
// as it is. About 0.15 s for 30 KB at 2 Mbit/s. The other tasks wait to print
// until it ends, so nothing lands inside it.
void sendPhoto(const Photo& photo, const char* kind = "JPEG") {
  ConsoleLock lock(true);
  Serial.printf("\x02-----BEGIN %s %u-----\n", kind, static_cast<unsigned>(photo.length));
  unsigned char line[1025];  // 768 bytes become 1,024 characters
  for (size_t i = 0; i < photo.length; i += 768) {
    size_t written = 0;
    mbedtls_base64_encode(line, sizeof(line), &written, photo.data + i, std::min<size_t>(768, photo.length - i));
    Serial.write(line, written);
    Serial.println();
  }
  Serial.printf("-----END %s-----\x03", kind);
}

// Gives the camera frame back however runScan returns.
struct HeldPhoto {
  Photo photo;
  ~HeldPhoto() { cameraRelease(photo); }
};

// Times every step from the press to the servo reaching the bin; "wait" is
// the rest of the upload, the server's work and the reply's trip back.
void runScan() {
  const uint32_t start = millis();
  ledShow(LedStage::Scanning);
  say("[scan] start\n");
  if (!cameraReady) return hold("camera not ready");
  if (!linkConfigured()) return hold("no server set: type \"server <url>\"");
  if (WiFi.status() != WL_CONNECTED) return hold("no Wi-Fi: type \"status\" to check it, or \"connect\"");

  HeldPhoto held;
  Photo& photo = held.photo;
  if (!cameraTake(photo)) return hold("photo failed");
  const uint32_t photoMs = millis() - start;
  printPhoto("[scan]", photo);
  const LinkReply r = linkPost(photo.data, photo.length, "image/jpeg");

  if (r.status <= 0) return hold("server unreachable: " + r.error);
  if (r.status == 401 || r.status == 403) {
    return hold("server refused the bin token (" + String(r.status) + "): check BIN_TOKEN in include/secrets.h");
  }
  if (r.status != 200) return hold("server answered " + String(r.status) + ": " + r.body.substring(0, 160));
  const uint32_t decideStart = millis();

  JsonDocument doc;
  const DeserializationError err = deserializeJson(doc, r.body);
  if (err) return hold(String("reply is not JSON: ") + err.c_str());
  if (!doc["objects"].is<JsonArrayConst>()) return hold("reply has no \"objects\" list: " + r.body.substring(0, 160));

  JsonArrayConst objects = doc["objects"].as<JsonArrayConst>();
  routing::Detection items[MAX_DETECTIONS];
  size_t count = 0;
  if (objects.size() == 0) say("[scan] detected nothing\n");
  for (JsonVariantConst object : objects) {
    const char* label = object["label"] | "";
    const double confidence = object["conf"] | 0.0;
    JsonArrayConst box = object["box"].as<JsonArrayConst>();
    say("[scan] detected %s %.2f box %d,%d,%d,%d\n", label, confidence, box[0] | 0, box[1] | 0, box[2] | 0,
        box[3] | 0);
    if (count < MAX_DETECTIONS) items[count++] = {label, confidence};
  }

  const float confidenceLimit = minConfidence;
  routing::Decision decision = routing::decide(items, count, confidenceLimit);
  String reason = describe(decision, confidenceLimit);
  if (objects.size() > MAX_DETECTIONS) {
    decision.stream = routing::Stream::Other;
    reason = "more than " + String(MAX_DETECTIONS) + " detections";
  }
  const Destination& destination = destinationFor(decision.stream);
  const int angle = destination.angle;
  say("[route] %s, liner %s: %s\n", destination.stream, destination.liners, reason.c_str());
  const uint32_t decideMs = millis() - decideStart;

  const uint32_t servoStart = millis();
  moveServo(angle);
  ledShow(LedStage::Sorted);
  const uint32_t now = millis();
  printTiming(photoMs, r.timing, decideMs, now - servoStart, now - start);
  sendPhoto(photo);  // during the dwell, so the viewer adds no time
  while (millis() - now < DWELL_MS) delay(1);
  moveServo(homeAngle);
  say("[scan] done\n");
}

void snap() {
  if (!cameraReady) return hold("camera not ready");
  Photo photo;
  if (!cameraTake(photo)) return hold("photo failed");
  printPhoto("[camera]", photo);
  sendPhoto(photo);
  cameraRelease(photo);
}

// ---- Automatic scans and the live view (worker) ----------------------------
// Every WATCH_INTERVAL_MS the camera compares the plate with the last check
// and with the empty plate. Once enough differs from the empty plate and
// nothing has moved for WATCH_STILL_CHECKS checks, the board scans. Things
// that move and leave nothing behind, such as a hand or a shadow, don't.
// While the viewer asks for the live view, every frame also goes to it, as
// fast as the cable carries them, and the plate is checked on each frame.

// Share of the pixels (0-1) that differ by more than WATCH_PIXEL_DIFF.
float changedShare(const uint8_t* a, const uint8_t* b) {
  int changed = 0;
  for (int i = 0; i < THUMB_PIXELS; ++i) changed += abs(a[i] - b[i]) > WATCH_PIXEL_DIFF;
  return static_cast<float>(changed) / THUMB_PIXELS;
}

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

  const float changed = watch.haveEmpty ? changedShare(watch.now, watch.empty) : 0;
  if (changed < WATCH_ITEM_SHARE) {
    if (!watch.haveEmpty) say("[watch] plate empty, watching\n");
    memcpy(watch.empty, watch.now, THUMB_PIXELS);  // also follows slow changes in the light
    watch.haveEmpty = true;
    return false;
  }
  say("[watch] %.1f%% of the plate changed and nothing moves: scanning\n", changed * 100);
  return true;
}

// The viewer's heartbeat keeps the live view on until this time.
std::atomic<uint32_t> liveUntil{0};
#ifdef AWARE_SIMULATOR
constexpr bool kLiveCamera = false;  // its "camera" hands out sim/photos in turn, one per scan
#else
constexpr bool kLiveCamera = true;
#endif
bool liveWanted() { return static_cast<int32_t>(liveUntil.load() - millis()) > 0; }

// One look at the plate: a frame for the live view, the automatic-scan check,
// or both.
void lookAtPlate() {
  static uint32_t watchedAt = 0;
  if (!kLiveCamera) return;
  const bool live = liveWanted();
  // The watch needs the plate at home ("servo" can leave it tipped), and
  // checks every WATCH_INTERVAL_MS even while the live view runs faster.
  const bool watching = autoScan && servoAngle == homeAngle && millis() - watchedAt >= WATCH_INTERVAL_MS;
  if (!cameraReady || (!live && !watching)) return;
  if (watching) watchedAt = millis();
  bool landed = false;
  {
    HeldPhoto frame;
    if (!cameraTake(frame.photo)) return;
    if (watching) landed = itemLanded(frame.photo);
    if (live) sendPhoto(frame.photo, "LIVE");
  }  // the frame goes back before the scan takes its own photo
  if (!landed) return;
  {
    Busy busy(Activity::Scanning);
    runScan();
  }
  watch.haveEmpty = false;  // whatever is still on the plate now counts as empty
  watch.stillChecks = 0;
}

void doWork(const Work& work) {
  switch (work.job) {
    case Job::Scan: {
      Busy busy(Activity::Scanning);
      scanQueued = false;
      runScan();
      break;
    }
    case Job::Snap: {
      Busy busy(Activity::Photo);
      snap();
      break;
    }
    case Job::Servo: {
      Busy busy(Activity::Servo);
      moveServo(work.angle);
      break;
    }
    case Job::CameraOff:
      if (cameraReady) {
        cameraReady = false;
        cameraEnd();
      }
      say("[camera] off: no automatic scans or live view until \"camera on\"\n");
      break;
    case Job::CameraOn:
      if (!cameraReady) {
        cameraReady = cameraBegin();
        if (cameraReady && jpegQuality != DEFAULT_JPEG_QUALITY) cameraSetQuality(jpegQuality);
      }
      break;
    case Job::ShowAngle: {
      Busy busy(Activity::Angle);
      visit(work.angle);
      break;
    }
  }
}

// Runs queued jobs in order; between them, looks at the plate.
void workerTask(void*) {
  for (;;) {
    ledUpdate();
    Work work;
    if (xQueueReceive(workQueue, &work, pdMS_TO_TICKS(liveWanted() ? 1 : 10)) == pdTRUE) {
      doWork(work);
    } else {
      lookAtPlate();
    }
  }
}

// ---- Wi-Fi (console) -------------------------------------------------------

// The radio takes the power in quarter dBm; it rounds to the steps it has.
void applyTxPower() { esp_wifi_set_max_tx_power(static_cast<int8_t>(wifiTxDbm * 4)); }

float txPowerNow() {
  int8_t quarters = 0;
  return esp_wifi_get_max_tx_power(&quarters) == ESP_OK ? quarters / 4.0f : 0;
}

// Starts joining and returns; reportWifiChanges says how it went.
void startJoin() {
  if (wifiSsid.isEmpty()) {
    say("[wifi] no network set. Type \"ssid <name>\", then \"pass <password>\", then \"connect\"\n");
    return;
  }
  say("[wifi] joining \"%s\"\n", wifiSsid.c_str());
  WiFi.disconnect();
#ifdef AWARE_SIMULATOR
  // Wokwi's access point is on channel 6; naming it skips a 4 s scan.
  if (wifiSsid == "Wokwi-GUEST") {
    WiFi.begin(wifiSsid.c_str(), wifiPass.c_str(), 6);
  } else {
    WiFi.begin(wifiSsid.c_str(), wifiPass.c_str());
  }
#else
  WiFi.begin(wifiSsid.c_str(), wifiPass.c_str());
#endif
  joining = true;
  joinStartedAt = millis();
}

void reportWifiChanges() {
  static bool wasConnected = false;
  const bool connected = WiFi.status() == WL_CONNECTED;
  if (connected != wasConnected) {
    wasConnected = connected;
    if (connected) {
      say("[wifi] connected, IP %s\n", WiFi.localIP().toString().c_str());
      linkConnectSoon();
    } else {
      say("[wifi] disconnected\n");
    }
  }
  if (connected) {
    joining = false;
  } else if (joining && millis() - joinStartedAt > WIFI_CONNECT_TIMEOUT_MS) {
    joining = false;
    say("[wifi] could not join. Check the name and password; the board only sees 2.4 GHz networks.\n");
  }
}

// ---- Prompt and status (console) -------------------------------------------

// Like zsh's robbyrussell theme ("➜  ~"): the arrow turns red after a failed
// command.
String buildPrompt() { return String(lastCommandOk ? "\x1b[1;32m" : "\x1b[1;31m") + "➜  \x1b[1;32maware-bin\x1b[0m "; }

String paint(const char* color, const String& text) { return String("\x1b[") + color + "m" + text + "\x1b[0m"; }

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

// "status", in the style of neofetch: the bin on the left, facts on the right.
void printStatus() {
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
  add("Camera", cameraReady ? String("simulator photos (no automatic scans)") : paint("31", "no simulator photos"));
#else
  add("Camera", cameraReady ? formatText("%s, 640x480, JPEG quality %d", cameraModel(), jpegQuality) : paint("31", "NOT ready"));
  add("Auto scan", autoScan ? String("on") : paint("33", "off"));
#endif
  const Activity now = activity;
  const unsigned waiting = waitingJobs();
  add("Bin", (now == Activity::Free ? paint("32", "free") : paint("33", activityText())) +
                 (waiting ? formatText(", %u command%s waiting", waiting, waiting == 1 ? "" : "s") : String()));
  if (kLiveCamera && liveWanted()) add("Live view", paint("32", "on") + ", to scripts/viewer.py");
  add("Servo", formatText("at %d°, %d°/s", servoAngle.load(), servoSpeed.load()));
  String angles = formatText("home %d", homeAngle.load());
  for (const auto& d : destinations) angles += formatText(", %s %d", d.stream, d.angle.load());
  add("Angles", angles);
  add("Routing", formatText("min confidence %.2f", minConfidence.load()));
  if (WiFi.status() == WL_CONNECTED) {
    add("Wi-Fi", "\"" + wifiSsid + "\" " + signalText(WiFi.RSSI()));
    add("IP", WiFi.localIP().toString() + formatText(", transmit power %.1f dBm", txPowerNow()));
  } else {
    add("Wi-Fi", "\"" + wifiSsid + "\" " + (joining ? paint("33", "joining") : paint("31", "not connected")));
  }
  String server = serverUrl;
  server.replace("https://", "");
  server.replace("http://", "");
  add("Server", serverUrl.isEmpty() ? paint("31", "not set")
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

// ---- Serial commands (console) ---------------------------------------------

// Prints why a command didn't work; the prompt's arrow turns red.
void fail(const char* text, ...) __attribute__((format(printf, 1, 2)));
void fail(const char* text, ...) {
  lastCommandOk = false;
  ConsoleLock lock;
  va_list args;
  va_start(args, text);
  Serial.vprintf(text, args);
  va_end(args);
}

// Hands a camera or servo job to the worker. Says so when it has to wait.
bool queueWork(const Work& work, const String& what) {
  const bool busy = activity.load() != Activity::Free;
  const char* now = activityText();
  const unsigned waiting = waitingJobs();
  if (xQueueSend(workQueue, &work, 0) != pdTRUE) {
    fail("[busy] %u commands are already waiting, so \"%s\" was skipped. Try again in a moment.\n", waiting,
         what.c_str());
    return false;
  }
  if (busy && waiting) {
    say("[busy] %s now; \"%s\" runs after that and %u waiting command%s\n", now, what.c_str(), waiting,
        waiting == 1 ? "" : "s");
  } else if (busy) {
    say("[busy] %s now; \"%s\" runs after that\n", now, what.c_str());
  } else if (waiting) {
    say("[busy] \"%s\" runs after %u waiting command%s\n", what.c_str(), waiting, waiting == 1 ? "" : "s");
  }
  return true;
}

void requestScan() {
  if (scanQueued || activity.load() == Activity::Scanning) {
    fail("[busy] a scan is already running or waiting, so this one was skipped\n");
    return;
  }
  scanQueued = true;
  if (!queueWork({Job::Scan, 0}, "scan")) scanQueued = false;
}

// For Tab: the commands, then the names after "angle" and "auto".
const char* const kCommands[] = {
    "angle", "auto", "camera", "conf", "connect", "feed", "help",
#ifdef AWARE_SIMULATOR
    "photo", "photos",
#endif
    "pass", "quality", "reboot", "scan", "servo", "server", "snap", "speed", "ssid", "status", "txpower",
};

void completeWords(const String& before, std::vector<const char*>& words) {
  const int space = before.indexOf(' ');
  if (space < 0) {
    words.assign(std::begin(kCommands), std::end(kCommands));
    return;
  }
  if (before.indexOf(' ', space + 1) >= 0) return;  // only the first two words
  String command = before.substring(0, space);
  command.toLowerCase();
  if (command == "angle") {
    words = {"home", "paper", "plastic_bottles", "other"};
  } else if (command == "auto" || command == "camera" || command == "feed") {
    words = {"on", "off"};
  }
}

void printHelp() {
  say("Commands:\n"
      "  status                 the bin at a glance\n"
      "  ssid <name>            Wi-Fi network name (2.4 GHz)\n"
      "  pass <password>        Wi-Fi password (empty for an open network)\n"
      "  connect                join the Wi-Fi network\n"
      "  server <url>           detection server address (https:// or http://)\n"
      "  conf <0.05-0.95>       lowest confidence routed to a recycling bin\n"
      "  speed <0-1000>         servo speed in degrees a second (0: as fast as it goes)\n"
      "  quality <4-63>         camera JPEG quality; lower is sharper but slower to send\n"
      "  txpower <2-21>         Wi-Fi transmit power in dBm (19.5 is the most)\n"
      "  servo <0-180>          turn the servo now (test)\n"
      "  angle <name> <0-180>   set and show the angle for home, paper, plastic_bottles or other\n"
      "  snap                   take a photo and send it to the viewer (camera test)\n"
#ifdef AWARE_SIMULATOR
      "  photos                 list the simulator's photos\n"
      "  photo <n>              send photo n on the next scan\n"
#endif
      "  scan                   photo -> server -> servo (same as the BOOT button)\n"
      "  auto on|off            scan by itself when an item lands (on after every start)\n"
      "  camera on|off          stop or start the camera (to test whether it disturbs Wi-Fi)\n"
      "  feed [off]             open (or close) the live camera window on the Mac\n"
      "  reboot                 restart the board\n"
      "Commands work at any time. scan, snap, servo and angle wait their turn\n"
      "while the camera or servo is busy.\n"
      "Keys: Up/Down history, Tab completes, Left/Right, Ctrl+A/E start/end,\n"
      "Ctrl+W deletes a word, Ctrl+U clears the line, Ctrl+L clears the screen.\n");
}

bool parseAngle(const String& text, int& angle) {
  if (text.isEmpty() || text.length() > 3) return false;
  for (size_t i = 0; i < text.length(); ++i) {
    if (!isDigit(text[i])) return false;
  }
  angle = text.toInt();
  return angle >= 0 && angle <= 180;
}

void setAngle(const String& arg) {
  const int space = arg.indexOf(' ');
  const String name = space < 0 ? arg : arg.substring(0, space);
  String value = space < 0 ? String() : arg.substring(space + 1);
  trimSpaces(value);
  int angle = 0;
  Destination* d = findDestination(name);
  if (!parseAngle(value, angle) || (!d && name != "home")) {
    fail("Usage: angle <home|paper|plastic_bottles|other> <0-180>\n");
    return;
  }
  if (!d) {
    homeAngle = angle;
    prefs.putInt("a_home", angle);
    say("Home angle saved: %d\n", angle);
    queueWork({Job::Servo, angle}, "angle home");
    return;
  }
  d->angle = angle;
  prefs.putInt(d->prefKey, angle);
  say("%s angle saved: %d. Showing it now.\n", d->stream, angle);
  queueWork({Job::ShowAngle, angle}, "angle " + name);
}

void setServer(String url) {
  while (url.endsWith("/")) url.remove(url.length() - 1);
  const bool valid = (url.startsWith("https://") && url.length() > 8) || (url.startsWith("http://") && url.length() > 7);
  if (!valid) {
    fail("Usage: server https://<address>\n");
    return;
  }
  String error;
  if (!linkSetServer(url, error)) {
    fail("Bad server address: %s\n", error.c_str());
    return;
  }
  serverUrl = url;
  prefs.putString("server", url);
  say("Server saved: %s. Connecting in the background.\n", url.c_str());
}

bool parseNumber(const String& text, int low, int high, int& value) {
  if (text.isEmpty() || text.length() > 4) return false;
  for (size_t i = 0; i < text.length(); ++i) {
    if (!isDigit(text[i])) return false;
  }
  value = text.toInt();
  return value >= low && value <= high;
}

void setSpeed(const String& arg) {
  int value = 0;
  if (!parseNumber(arg, 0, 1000, value)) {
    fail("Usage: speed <0-1000>   (degrees a second; 0 = as fast as the servo goes)\n");
    return;
  }
  servoSpeed = value;
  prefs.putInt("servo_dps", value);
  say("Servo speed saved: %d deg/s\n", value);
}

void setQuality(const String& arg) {
  int value = 0;
  if (!parseNumber(arg, 4, 63, value)) {
    fail("Usage: quality <4-63>   (lower is sharper and bigger)\n");
    return;
  }
  jpegQuality = value;
  prefs.putInt("jpeg_q", value);
  cameraSetQuality(value);
  say("JPEG quality saved: %d\n", value);
}

void setMinConfidence(const String& arg) {
  const float value = arg.toFloat();
  if (arg.isEmpty() || value < 0.05f || value > 0.95f) {
    fail("Usage: conf <0.05-0.95>\n");
    return;
  }
  minConfidence = value;
  prefs.putFloat("min_conf", value);
  say("Min confidence saved: %.2f\n", value);
}

void handleCommand(String line) {
  lastCommandOk = true;
  trimSpaces(line);
  const int space = line.indexOf(' ');
  String cmd = space < 0 ? line : line.substring(0, space);
  String arg = space < 0 ? String() : line.substring(space + 1);
  cmd.toLowerCase();
  trimSpaces(arg);

  if (cmd == "help") {
    printHelp();
  } else if (cmd == "status") {
    printStatus();
  } else if (cmd == "ssid") {
    wifiSsid = arg;
    prefs.putString("ssid", arg);
    say("Network saved: \"%s\". Now type \"pass <password>\", then \"connect\"\n", arg.c_str());
  } else if (cmd == "pass") {
    wifiPass = arg;
    prefs.putString("pass", arg);
    say("%s\n", arg.isEmpty() ? "Password cleared (open network)." : "Password saved. Type \"connect\"");
  } else if (cmd == "connect") {
    startJoin();
  } else if (cmd == "server") {
    setServer(arg);
  } else if (cmd == "conf") {
    setMinConfidence(arg);
  } else if (cmd == "speed") {
    setSpeed(arg);
  } else if (cmd == "txpower") {
    const float value = arg.toFloat();
    if (arg.isEmpty() || value < 2 || value > 21) {
      fail("Usage: txpower <2-21>   (dBm; 19.5 is the most)\n");
    } else {
      wifiTxDbm = value;
      prefs.putFloat("tx_dbm", value);
      applyTxPower();
      say("Wi-Fi transmit power saved: %.1f dBm (the radio uses %.1f)\n", value, txPowerNow());
    }
  } else if (cmd == "quality") {
    setQuality(arg);
  } else if (cmd == "servo") {
    int angle = 0;
    if (parseAngle(arg, angle)) {
      queueWork({Job::Servo, angle}, "servo " + arg);
    } else {
      fail("Usage: servo <0-180>\n");
    }
  } else if (cmd == "angle") {
    setAngle(arg);
  } else if (cmd == "snap") {
    queueWork({Job::Snap, 0}, "snap");
  } else if (cmd == "feed" && (arg.isEmpty() || arg == "on")) {
    // The PlatformIO monitor's aware_feed filter (monitor/filter_aware_feed.py)
    // sees this line and opens scripts/viewer.py, which then keeps the stream on.
    say(kLiveCamera ? "[feed] opening the live view on the Mac\n"
                    : "[feed] opening the live view on the Mac (the simulator has no live camera)\n");
  } else if (cmd == "feed" && arg == "off") {
    liveUntil = millis();  // stop streaming now, not after LIVE_HOLD_MS
    say("[feed] closing the live view\n");
  } else if (cmd == "feed") {
    fail("Usage: feed [off]\n");
  } else if (cmd == "camera" && (arg == "on" || arg == "off")) {
    queueWork({arg == "on" ? Job::CameraOn : Job::CameraOff, 0}, "camera " + arg);
  } else if (cmd == "camera") {
    fail("Usage: camera on|off\n");
  } else if (cmd == "auto") {
    autoScan = arg != "off";
    say("Automatic scans %s\n", autoScan ? "on" : "off");
  } else if (cmd == "photos") {
    lastCommandOk = cameraListPhotos();
  } else if (cmd == "photo") {
    lastCommandOk = cameraChoosePhoto(arg.toInt());
  } else if (cmd == "scan") {
    requestScan();
  } else if (cmd == "reboot") {
    ESP.restart();
  } else {
    fail("Unknown command \"%s\". Type \"help\" for all commands.\n", cmd.c_str());
  }
}

void pollButton() {
  static bool pressed = false;
  static uint32_t changedAt = 0;
  const bool now = digitalRead(BUTTON_PIN) == LOW;
  if (now != pressed && millis() - changedAt > BUTTON_DEBOUNCE_MS) {
    pressed = now;
    changedAt = millis();
    if (pressed) requestScan();
  }
}

}  // namespace

void setup() {
  Serial.begin(SERIAL_BAUD);  // fast enough for the live view and a photo within the dwell
  delay(500);
  consoleBegin();
  consoleSetCompleter(completeWords);
  consoleSetHeartbeat([] { liveUntil = millis() + LIVE_HOLD_MS; });
  // The console (this task) runs ahead of the worker and link tasks, so it
  // answers at once. It only ever waits briefly.
  vTaskPrioritySet(nullptr, 2);
#ifdef AWARE_SIMULATOR
  say("\nAWARE bin MVP %s (Wokwi simulator)\n", FIRMWARE_VERSION);
#else
  say("\nAWARE bin MVP %s\n", FIRMWARE_VERSION);
#endif

  pinMode(BUTTON_PIN, INPUT_PULLUP);
  loadSettings();
  ledBegin();

  // A fixed channel keeps the servo off channel 0, which the camera clock uses.
  if (!ledcAttachChannel(SERVO_PIN, SERVO_FREQ_HZ, SERVO_LEDC_BITS, SERVO_LEDC_CHANNEL)) {
    say("[servo] could not set up the servo signal\n");
  }
  writeServo(homeAngle);

  cameraReady = cameraBegin();
  if (cameraReady && jpegQuality != DEFAULT_JPEG_QUALITY) cameraSetQuality(jpegQuality);

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.setAutoReconnect(true);
  applyTxPower();
  deviceId = macAddress();
  linkBegin();
  if (!serverUrl.isEmpty()) {
    String error;
    if (!linkSetServer(serverUrl, error)) say("[link] bad server address: %s\n", error.c_str());
  }
  if (!wifiSsid.isEmpty()) startJoin();  // the link connects once Wi-Fi has joined

  workQueue = xQueueCreate(WORK_QUEUE_LENGTH, sizeof(Work));
  xTaskCreatePinnedToCore(workerTask, "bin-worker", WORKER_TASK_STACK_BYTES, nullptr, 1, nullptr, xPortGetCoreID());

  printStatus();
  say("Ready. Press BOOT or type \"scan\". Type \"help\" for all commands.\n");
  consoleSetPrompt(buildPrompt());
  consoleStartPrompt();
}

void loop() {
  String line;
  if (consoleReadLine(line)) {
    ConsoleLock lock;  // the prompt comes back, updated, when the command ends
    handleCommand(line);
    consoleSetPrompt(buildPrompt());
  }
  pollButton();
  reportWifiChanges();
  delay(5);
}
