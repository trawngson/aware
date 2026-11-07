// AWARE bin MVP: one ESP32-S3 camera board and one servo.
//
// Press the BOOT button (or type "scan"): the board photographs the plate,
// sends the JPEG to the detection server, routes the detections with the
// routing-v1 rules, and turns the servo to that stream's angle. It holds
// there, then returns home. On any failure it holds: the servo stays home.

#include <Arduino.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <WiFi.h>

#include <algorithm>

#include "camera.h"
#include "mbedtls/base64.h"
#include "config.h"
#include "routing.h"
#include "server_link.h"

namespace {

struct Destination {
  const char* stream;   // routing-v1 stream
  const char* prefKey;  // where its angle is saved
  int defaultAngle;
  const char* liners;   // routing-v1 liners, for the log
  int angle;
};

Destination destinations[] = {
    {"paper", "a_paper", DEFAULT_ANGLE_PAPER, "1", 0},
    {"plastic_bottles", "a_bottles", DEFAULT_ANGLE_BOTTLES, "2", 0},
    {"other", "a_other", DEFAULT_ANGLE_OTHER, "3 and 4", 0},
};
// Same order as routing::Stream.
Destination& destinationFor(routing::Stream stream) { return destinations[static_cast<int>(stream)]; }

Preferences prefs;
String wifiSsid;
String wifiPass;
String serverUrl;
String deviceId;
String inputLine;
float minConfidence = DEFAULT_MIN_CONFIDENCE;
int homeAngle = DEFAULT_ANGLE_HOME;
int servoAngle = -1;
int servoSpeed = DEFAULT_SERVO_SPEED_DPS;
int jpegQuality = DEFAULT_JPEG_QUALITY;
bool cameraReady = false;
bool autoScan = true;  // watchPlate; "auto off" stops it until the next start

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
}

// ---- Servo -----------------------------------------------------------------

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
  if (servoAngle == target) return;
  if (servoAngle < 0 || servoSpeed <= 0) {
    if (servoAngle >= 0) Serial.printf("[servo] %d -> %d\n", servoAngle, target);
    writeServo(target);
    return;
  }
  Serial.printf("[servo] %d -> %d\n", servoAngle, target);
  const int from = servoAngle;
  const int steps = abs(target - from);
  const int direction = target > from ? 1 : -1;
  const uint32_t start = millis();
  for (int i = 1; i <= steps; ++i) {
    writeServo(from + direction * i);
    const uint32_t due = start + static_cast<uint32_t>(i) * 1000u / static_cast<uint32_t>(servoSpeed);
    while (static_cast<int32_t>(millis() - due) < 0) delay(1);
  }
}

void visit(int angle) {
  moveServo(angle);
  delay(DWELL_MS);
  moveServo(homeAngle);
}

// ---- Wi-Fi and server ------------------------------------------------------

bool connectWifi() {
  if (wifiSsid.isEmpty()) {
    Serial.println("[wifi] no network set. Type  ssid <name>  then  pass <password>  then  connect");
    return false;
  }
  Serial.printf("[wifi] joining \"%s\"", wifiSsid.c_str());
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
  const uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < WIFI_CONNECT_TIMEOUT_MS) {
    delay(500);
    Serial.print('.');
  }
  Serial.println();
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[wifi] could not join. Check the name and password; the board only sees 2.4 GHz networks.");
    return false;
  }
  Serial.printf("[wifi] connected, IP %s\n", WiFi.localIP().toString().c_str());
  return true;
}

// ---- Routing ---------------------------------------------------------------

String describe(const routing::Decision& d) {
  switch (d.reason) {
    case routing::Reason::OneStream:
      return String("every item goes to ") + routing::streamName(d.stream);
    case routing::Reason::NothingDetected:
      return "nothing detected";
    case routing::Reason::LowConfidence:
      return String(d.label) + " is below confidence " + String(minConfidence, 2);
    case routing::Reason::UnknownLabel:
      return String("\"") + d.label + "\" is not a bin class";
    case routing::Reason::Mixed:
      return "the items belong in more than one bin";
  }
  return "";
}

// ---- Scan ------------------------------------------------------------------

void printPhoto(const char* tag, const Photo& photo) {
  Serial.printf("%s photo %ux%u, %u KB", tag, photo.width, photo.height, static_cast<unsigned>(photo.length / 1024));
  if (photo.name) Serial.printf(" (%s)", photo.name);
  Serial.println();
}

void hold(const String& why) {
  Serial.printf("[hold] %s. The servo stays home.\n", why.c_str());
}

void printTiming(uint32_t photoMs, const LinkTiming& t, uint32_t decideMs, uint32_t servoMs, uint32_t totalMs) {
  Serial.printf("[time] photo %u | connect %u%s | send %u | wait %u | read %u | decide %u | servo %u | total %u ms\n",
                static_cast<unsigned>(photoMs), static_cast<unsigned>(t.connectMs),
                t.reused ? " (kept open)" : " (new connection)", static_cast<unsigned>(t.sendMs),
                static_cast<unsigned>(t.waitMs), static_cast<unsigned>(t.readMs), static_cast<unsigned>(decideMs),
                static_cast<unsigned>(servoMs), static_cast<unsigned>(totalMs));
}

// Sends the photo as base64 text between two marker lines for
// scripts/viewer.py on the Mac. About 0.45 s for 30 KB at 921600 baud.
void sendPhoto(const Photo& photo) {
  Serial.printf("-----BEGIN JPEG %u-----\n", static_cast<unsigned>(photo.length));
  unsigned char line[1025];  // 768 bytes become 1,024 characters
  for (size_t i = 0; i < photo.length; i += 768) {
    size_t written = 0;
    mbedtls_base64_encode(line, sizeof(line), &written, photo.data + i, std::min<size_t>(768, photo.length - i));
    Serial.write(line, written);
    Serial.println();
  }
  Serial.println("-----END JPEG-----");
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
  Serial.println("[scan] start");
  if (!cameraReady) return hold("camera not ready");
  if (serverUrl.isEmpty()) return hold("no server set: type  server <url>");
  if (WiFi.status() != WL_CONNECTED && !connectWifi()) return hold("no Wi-Fi");

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
  if (objects.size() == 0) Serial.println("[scan] detected nothing");
  for (JsonVariantConst object : objects) {
    const char* label = object["label"] | "";
    const double confidence = object["conf"] | 0.0;
    JsonArrayConst box = object["box"].as<JsonArrayConst>();
    Serial.printf("[scan] detected %s %.2f box %d,%d,%d,%d\n", label, confidence, box[0] | 0, box[1] | 0,
                  box[2] | 0, box[3] | 0);
    if (count < MAX_DETECTIONS) items[count++] = {label, confidence};
  }

  routing::Decision decision = routing::decide(items, count, minConfidence);
  String reason = describe(decision);
  if (objects.size() > MAX_DETECTIONS) {
    decision.stream = routing::Stream::Other;
    reason = "more than " + String(MAX_DETECTIONS) + " detections";
  }
  const Destination& destination = destinationFor(decision.stream);
  Serial.printf("[route] %s, liner %s: %s\n", destination.stream, destination.liners, reason.c_str());
  const uint32_t decideMs = millis() - decideStart;

  const uint32_t servoStart = millis();
  moveServo(destination.angle);
  const uint32_t now = millis();
  printTiming(photoMs, r.timing, decideMs, now - servoStart, now - start);
  sendPhoto(photo);  // during the dwell, so the viewer adds no time
  while (millis() - now < DWELL_MS) delay(1);
  moveServo(homeAngle);
  Serial.println("[scan] done");
}

void snap() {
  if (!cameraReady) return hold("camera not ready");
  Photo photo;
  if (!cameraTake(photo)) return hold("photo failed");
  printPhoto("[camera]", photo);
  sendPhoto(photo);
  cameraRelease(photo);
}

// ---- Automatic scans -------------------------------------------------------
// Every WATCH_INTERVAL_MS the camera compares the plate with the last check
// and with the empty plate. Once enough differs from the empty plate and
// nothing has moved for WATCH_STILL_CHECKS checks, the board scans. Things
// that move and leave nothing behind, such as a hand or a shadow, don't.

// Share of the pixels (0-1) that differ by more than WATCH_PIXEL_DIFF.
float changedShare(const uint8_t* a, const uint8_t* b) {
  int changed = 0;
  for (int i = 0; i < THUMB_PIXELS; ++i) changed += abs(a[i] - b[i]) > WATCH_PIXEL_DIFF;
  return static_cast<float>(changed) / THUMB_PIXELS;
}

void watchPlate() {
  static uint8_t empty[THUMB_PIXELS], last[THUMB_PIXELS], now[THUMB_PIXELS];
  static bool haveEmpty = false;
  static int stillChecks = 0;
  static uint32_t checkedAt = 0;
  // Only with the plate at home: "servo" can leave it tipped.
  if (!autoScan || !cameraReady || servoAngle != homeAngle) return;
  if (millis() - checkedAt < WATCH_INTERVAL_MS) return;
  checkedAt = millis();
  if (!cameraThumbnail(now)) return;

  stillChecks = changedShare(now, last) < WATCH_STILL_SHARE ? stillChecks + 1 : 0;
  memcpy(last, now, THUMB_PIXELS);
  if (stillChecks < WATCH_STILL_CHECKS) return;

  const float changed = haveEmpty ? changedShare(now, empty) : 0;
  if (changed < WATCH_ITEM_SHARE) {
    if (!haveEmpty) Serial.println("[watch] plate empty, watching");
    memcpy(empty, now, THUMB_PIXELS);  // also follows slow changes in the light
    haveEmpty = true;
    return;
  }
  Serial.printf("[watch] %.1f%% of the plate changed and nothing moves: scanning\n", changed * 100);
  runScan();
  haveEmpty = false;  // whatever is still on the plate now counts as empty
  stillChecks = 0;
}

// ---- Serial commands -------------------------------------------------------

void printHelp() {
  Serial.println(
      "Commands:\n"
      "  status                 show settings and connection\n"
      "  ssid <name>            Wi-Fi network name (2.4 GHz)\n"
      "  pass <password>        Wi-Fi password (empty for an open network)\n"
      "  connect                join the Wi-Fi network\n"
      "  server <url>           detection server address (https:// or http://)\n"
      "  conf <0.05-0.95>       lowest confidence routed to a recycling bin\n"
      "  speed <0-1000>         servo speed in degrees a second (0: as fast as it goes)\n"
      "  quality <4-63>         camera JPEG quality; lower is sharper but slower to send\n"
      "  servo <0-180>          turn the servo now (test)\n"
      "  angle <name> <0-180>   set and show the angle for home, paper, plastic_bottles or other\n"
      "  snap                   take a photo and send it to the viewer (camera test)\n"
#ifdef AWARE_SIMULATOR
      "  photos                 list the simulator's photos\n"
      "  photo <n>              send photo n on the next scan\n"
#endif
      "  scan                   photo -> server -> servo (same as the BOOT button)\n"
      "  auto on|off            scan by itself when an item lands (on after every start)\n"
      "  reboot                 restart the board");
}

void printStatus() {
  Serial.printf("Firmware %s, device %s\n", FIRMWARE_VERSION, deviceId.c_str());
#ifdef AWARE_SIMULATOR
  Serial.printf("Camera: simulator photos%s (no automatic scans), PSRAM: %s\n", cameraReady ? "" : " (none)",
                psramFound() ? "yes" : "no");
#else
  Serial.printf("Camera: %s, PSRAM: %s, automatic scans: %s\n", cameraReady ? "ready" : "NOT ready",
                psramFound() ? "yes" : "no", autoScan ? "on" : "off");
#endif
  Serial.printf("Wi-Fi: \"%s\" %s", wifiSsid.c_str(), WiFi.status() == WL_CONNECTED ? "connected" : "not connected");
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf(", IP %s, signal %d dBm", WiFi.localIP().toString().c_str(), WiFi.RSSI());
  }
  Serial.println();
  Serial.printf("Server: %s, connection %s\n", serverUrl.isEmpty() ? "(not set)" : serverUrl.c_str(),
                linkIsOpen() ? "open" : "closed");
  Serial.printf("Min confidence: %.2f, servo speed: %d deg/s, JPEG quality: %d\n", minConfidence, servoSpeed,
                jpegQuality);
  Serial.printf("Angles: home %d", homeAngle);
  for (const auto& d : destinations) Serial.printf(", %s %d", d.stream, d.angle);
  Serial.printf(" (servo now %d)\n", servoAngle);
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
  value.trim();
  int angle = 0;
  Destination* d = findDestination(name);
  if (!parseAngle(value, angle) || (!d && name != "home")) {
    Serial.println("Usage: angle <home|paper|plastic_bottles|other> <0-180>");
    return;
  }
  if (!d) {
    homeAngle = angle;
    prefs.putInt("a_home", angle);
    moveServo(angle);
    Serial.printf("Home angle saved: %d\n", angle);
    return;
  }
  d->angle = angle;
  prefs.putInt(d->prefKey, angle);
  Serial.printf("%s angle saved: %d. Showing it now.\n", d->stream, angle);
  visit(angle);
}

void setServer(String url) {
  while (url.endsWith("/")) url.remove(url.length() - 1);
  const bool valid = (url.startsWith("https://") && url.length() > 8) || (url.startsWith("http://") && url.length() > 7);
  if (!valid) {
    Serial.println("Usage: server https://<address>");
    return;
  }
  String error;
  if (!linkSetServer(url, error)) {
    Serial.printf("Bad server address: %s\n", error.c_str());
    return;
  }
  serverUrl = url;
  prefs.putString("server", url);
  Serial.printf("Server saved: %s\n", url.c_str());
  linkConnect();
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
    Serial.println("Usage: speed <0-1000>   (degrees a second; 0 = as fast as the servo goes)");
    return;
  }
  servoSpeed = value;
  prefs.putInt("servo_dps", value);
  Serial.printf("Servo speed saved: %d deg/s\n", value);
}

void setQuality(const String& arg) {
  int value = 0;
  if (!parseNumber(arg, 4, 63, value)) {
    Serial.println("Usage: quality <4-63>   (lower is sharper and bigger)");
    return;
  }
  jpegQuality = value;
  prefs.putInt("jpeg_q", value);
  cameraSetQuality(value);
  Serial.printf("JPEG quality saved: %d\n", value);
}

void setMinConfidence(const String& arg) {
  const float value = arg.toFloat();
  if (arg.isEmpty() || value < 0.05f || value > 0.95f) {
    Serial.println("Usage: conf <0.05-0.95>");
    return;
  }
  minConfidence = value;
  prefs.putFloat("min_conf", value);
  Serial.printf("Min confidence saved: %.2f\n", value);
}

void handleCommand(String line) {
  line.trim();
  const int space = line.indexOf(' ');
  String cmd = space < 0 ? line : line.substring(0, space);
  String arg = space < 0 ? String() : line.substring(space + 1);
  cmd.toLowerCase();
  arg.trim();

  if (cmd == "help") {
    printHelp();
  } else if (cmd == "status") {
    printStatus();
  } else if (cmd == "ssid") {
    wifiSsid = arg;
    prefs.putString("ssid", arg);
    Serial.printf("Network saved: \"%s\". Now type  pass <password>  then  connect\n", arg.c_str());
  } else if (cmd == "pass") {
    wifiPass = arg;
    prefs.putString("pass", arg);
    Serial.println(arg.isEmpty() ? "Password cleared (open network)." : "Password saved. Type  connect");
  } else if (cmd == "connect") {
    connectWifi();
  } else if (cmd == "server") {
    setServer(arg);
  } else if (cmd == "conf") {
    setMinConfidence(arg);
  } else if (cmd == "speed") {
    setSpeed(arg);
  } else if (cmd == "quality") {
    setQuality(arg);
  } else if (cmd == "servo") {
    int angle = 0;
    if (parseAngle(arg, angle)) {
      moveServo(angle);
    } else {
      Serial.println("Usage: servo <0-180>");
    }
  } else if (cmd == "angle") {
    setAngle(arg);
  } else if (cmd == "snap") {
    snap();
  } else if (cmd == "auto") {
    autoScan = arg != "off";
    Serial.printf("Automatic scans %s\n", autoScan ? "on" : "off");
  } else if (cmd == "photos") {
    cameraListPhotos();
  } else if (cmd == "photo") {
    cameraChoosePhoto(arg.toInt());
  } else if (cmd == "scan") {
    runScan();
  } else if (cmd == "reboot") {
    ESP.restart();
  } else {
    Serial.printf("Unknown command \"%s\". Type  help\n", cmd.c_str());
  }
}

// Echoes what is typed, so any serial terminal works.
void pollSerial() {
  while (Serial.available()) {
    const char c = static_cast<char>(Serial.read());
    if (c == '\r' || c == '\n') {
      if (!inputLine.isEmpty()) {
        Serial.println();
        handleCommand(inputLine);
        inputLine = "";
      }
    } else if (c == 8 || c == 127) {
      if (!inputLine.isEmpty()) {
        inputLine.remove(inputLine.length() - 1);
        Serial.print("\b \b");
      }
    } else if (isPrintable(c) && inputLine.length() < 200) {
      inputLine += c;
      Serial.print(c);
    }
  }
}

void pollButton() {
  static bool pressed = false;
  static uint32_t changedAt = 0;
  const bool now = digitalRead(BUTTON_PIN) == LOW;
  if (now != pressed && millis() - changedAt > BUTTON_DEBOUNCE_MS) {
    pressed = now;
    changedAt = millis();
    if (pressed) runScan();
  }
}

void reportWifiChanges() {
  static bool wasConnected = false;
  const bool connected = WiFi.status() == WL_CONNECTED;
  if (connected == wasConnected) return;
  wasConnected = connected;
  if (connected) {
    Serial.printf("[wifi] connected, IP %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("[wifi] disconnected");
  }
}

}  // namespace

void setup() {
  Serial.begin(921600);  // fast enough to send a photo within the dwell
  delay(500);
#ifdef AWARE_SIMULATOR
  Serial.printf("\nAWARE bin MVP %s (Wokwi simulator)\n", FIRMWARE_VERSION);
#else
  Serial.printf("\nAWARE bin MVP %s\n", FIRMWARE_VERSION);
#endif

  pinMode(BUTTON_PIN, INPUT_PULLUP);
  loadSettings();

  // A fixed channel keeps the servo off channel 0, which the camera clock uses.
  if (!ledcAttachChannel(SERVO_PIN, SERVO_FREQ_HZ, SERVO_LEDC_BITS, SERVO_LEDC_CHANNEL)) {
    Serial.println("[servo] could not set up the servo signal");
  }
  writeServo(homeAngle);

  cameraReady = cameraBegin();
  if (cameraReady && jpegQuality != DEFAULT_JPEG_QUALITY) cameraSetQuality(jpegQuality);

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.setAutoReconnect(true);
  deviceId = WiFi.macAddress();
  if (!serverUrl.isEmpty()) {
    String error;
    if (!linkSetServer(serverUrl, error)) Serial.printf("[link] bad server address: %s\n", error.c_str());
  }
  if (!wifiSsid.isEmpty() && connectWifi()) linkConnect();

  printStatus();
  Serial.println("Ready. Press BOOT or type  scan . Type  help  for all commands.");
}

void loop() {
  pollSerial();
  pollButton();
  reportWifiChanges();
  linkMaintain();
  watchPlate();
  delay(5);
}
