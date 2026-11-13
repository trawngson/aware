#include "scan.h"

#include <Arduino.h>
#include <ArduinoJson.h>
#include <WiFi.h>

#include <algorithm>
#include <memory>
#include <new>

#include "config.h"
#include "console.h"
#include "imu.h"
#include "llm.h"
#include "llm_reply.h"
#include "mbedtls/base64.h"
#include "routing.h"
#include "server_link.h"
#include "servo.h"
#include "settings.h"
#include "status_led.h"
#include "worker.h"

namespace {

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

void printPhoto(const char* tag, const Photo& photo) {
  say("%s photo %ux%u, %u KB%s%s%s\n", tag, photo.width, photo.height, static_cast<unsigned>(photo.length / 1024),
      photo.name ? " (" : "", photo.name ? photo.name : "", photo.name ? ")" : "");
}

void hold(const String& why) {
  ledShow(LedStage::Error);
  say("[hold] %s. The servo stays home.\n", why.c_str());
}

// hold() for the functions that return whether the scan goes on.
bool held(const String& why) {
  hold(why);
  return false;
}

void printTiming(uint32_t photoMs, const LinkTiming& t, uint32_t decideMs, uint32_t servoMs, uint32_t totalMs) {
  say("[time] photo %u | connect %u%s | send %u | wait %u | read %u | decide %u | servo %u | total %u ms\n",
      static_cast<unsigned>(photoMs), static_cast<unsigned>(t.connectMs), t.reused ? " (kept open)" : " (new connection)",
      static_cast<unsigned>(t.sendMs), static_cast<unsigned>(t.waitMs), static_cast<unsigned>(t.readMs),
      static_cast<unsigned>(decideMs), static_cast<unsigned>(servoMs), static_cast<unsigned>(totalMs));
}

// The items on the plate, from the detection server's boxes or the model's
// list. The labels point into doc or answer, which live as long as this.
struct Found {
  routing::Detection items[MAX_DETECTIONS];
  size_t count = 0;
  bool tooMany = false;       // more than MAX_DETECTIONS: the plate goes to other
  float confidenceLimit = 0;  // 0 for the model, which gives no confidence
  JsonDocument doc;
  llm::Answer answer;
};
static_assert(llm::kMaxItems <= MAX_DETECTIONS, "every item the model lists must fit");

// The detection server's reply: {"objects": [{"label", "conf", "box"}]}.
// False once it has held.
bool readDetections(const LinkReply& r, Found& found) {
  if (r.status <= 0) return held("server unreachable: " + r.error);
  if (r.status == 401 || r.status == 403) {
    return held("server refused the bin token (" + String(r.status) + "): check BIN_TOKEN in include/secrets.h");
  }
  if (r.status != 200) return held("server answered " + String(r.status) + ": " + r.body.substring(0, 160));
  const DeserializationError err = deserializeJson(found.doc, r.body);
  if (err) return held(String("reply is not JSON: ") + err.c_str());
  if (!found.doc["objects"].is<JsonArrayConst>()) {
    return held("reply has no \"objects\" list: " + r.body.substring(0, 160));
  }
  JsonArrayConst objects = found.doc["objects"].as<JsonArrayConst>();
  if (objects.size() == 0) say("[scan] detected nothing\n");
  for (JsonVariantConst object : objects) {
    const char* label = object["label"] | "";
    const double confidence = object["conf"] | 0.0;
    JsonArrayConst box = object["box"].as<JsonArrayConst>();
    say("[scan] detected %s %.2f box %d,%d,%d,%d\n", label, confidence, box[0] | 0, box[1] | 0, box[2] | 0,
        box[3] | 0);
    if (found.count < MAX_DETECTIONS) found.items[found.count++] = {label, confidence};
  }
  found.tooMany = objects.size() > MAX_DETECTIONS;
  found.confidenceLimit = settings::minConfidence;
  return true;
}

// The model's reply: streamed events with {"items": [{"label"}]} as the
// answer (llm_reply.h). False once it has held.
bool readModelAnswer(const LinkReply& r, const String& model, Found& found) {
  if (r.status <= 0) return held("ChatGPT unreachable: " + r.error);
  const String text = llm::errorText(r.body.c_str(), r.body.length()).c_str();
  if (r.status == 401) {
    llmRenewSoon();
    return held("ChatGPT refused the bin's sign-in (401: " + text + "). Renewing it: scan again in a moment");
  }
  if (r.status == 429) return held("ChatGPT usage limit reached (429): " + text);
  if (r.status != 200) return held("ChatGPT answered " + String(r.status) + ": " + text);
  found.answer = llm::readAnswer(r.body.c_str(), r.body.length());
  if (!found.answer.ok) return held("no answer from " + model + ": " + found.answer.error.c_str());
  String seen;
  for (size_t i = 0; i < found.answer.count; ++i) {
    found.items[i] = {found.answer.labels[i], 1.0};
    seen += (i ? ", " : "") + String(found.answer.labels[i]);
  }
  found.count = found.answer.count;
  found.tooMany = found.answer.tooMany;
  found.confidenceLimit = 0;  // the model gives no confidence, so "conf" doesn't apply
  say("[scan] %s saw %s\n", model.c_str(), found.count ? seen.c_str() : "nothing");
  return true;
}

// After a tip (IMU in use): how far the plate went at the bin and whether it
// came back level. Red LED if it didn't tip or isn't level now; the next
// scan holds until it is.
void checkTip(int angle, const ImuReading& atBin) {
  if (!imuInUse() || !atBin.present) return;
  const ImuReading home = imuSettle();
  if (!home.present) return;
  say("[imu] tipped to %.1f°, back at %.1f°\n", atBin.tiltDeg, home.tiltDeg);
  if (angle != settings::homeAngle && atBin.tiltDeg < IMU_MIN_TIP_DEG) {
    ledShow(LedStage::Error);
    say("[imu] the plate tipped only %.1f° at the bin (servo %d°): stuck, or the servo stalled?\n", atBin.tiltDeg,
        angle);
  }
  if (home.tiltDeg > IMU_LEVEL_TOLERANCE_DEG) {
    ledShow(LedStage::Error);
    say("[imu] the plate is %.1f° off level back home: scans hold until it is level\n", home.tiltDeg);
  }
}

}  // namespace

void sendPhoto(const Photo& photo, const char* kind) {
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

// Times every step from the press to the servo reaching the bin; "wait" is
// the rest of the upload, the server's (or model's) work and the reply's trip
// back.
void runScan() {
  const uint32_t start = millis();
  const ScanSettings current = settings::forScan();
  const bool llmMode = current.mode == Mode::Llm;
  ledShow(LedStage::Scanning);
  say("[scan] start\n");  // exactly: scripts/viewer.py starts a new scan on it
  imuUseImpacts();       // whatever landed is this scan's
  if (!cameraReady) return hold("camera not ready");
  if (llmMode && !llmSignedIn()) return hold("not signed in to ChatGPT: type \"llm login\"");
  if (!llmMode && current.serverUrl.isEmpty()) return hold("no server set: type \"server <url>\"");
  if (WiFi.status() != WL_CONNECTED) return hold("no Wi-Fi: type \"status\" to check it, or \"connect\"");
  if (imuInUse()) {
    const ImuReading r = imuSettle();
    if (r.present && r.tiltDeg > IMU_LEVEL_TOLERANCE_DEG) {
      return hold("the plate is " + String(r.tiltDeg, 1) +
                  "° off level at home. Check the home angle (\"angle home\"), or if it is level, type \"imu level\"");
    }
  }

  HeldPhoto held;
  Photo& photo = held.photo;
  if (!cameraTake(photo)) return hold("photo failed");
  const uint32_t photoMs = millis() - start;
  printPhoto("[scan]", photo);
  if (llmMode) say("[scan] asking %s\n", current.model.c_str());

  LinkRequest request;
  LlmRequest llmRequest;  // owns the body in LLM mode
  if (llmMode) {
    String error;
    if (!llmBuildRequest(photo.data, photo.length, current.model, llmRequest, error)) return hold(error);
    request.url = LLM_URL;
    request.body = llmRequest.data;
    request.length = llmRequest.length;
    request.contentType = "application/json";
    request.accept = "text/event-stream";
    request.headers = llmRequest.headers;
    request.maxReplyBytes = LLM_MAX_REPLY_BYTES;
    request.timeoutMs = LLM_TIMEOUT_MS;
  } else {
    request.url = current.serverUrl;
    request.body = photo.data;
    request.length = photo.length;
    request.contentType = "image/jpeg";
    request.headers = "X-Bin-Token: " BIN_TOKEN "\r\n";
  }
  const LinkReply r = linkPost(request);
  const uint32_t decideStart = millis();

  // On the heap: the worker's stack is sized for a TLS handshake, not for this.
  std::unique_ptr<Found> found(new (std::nothrow) Found);
  if (!found) return hold("out of memory reading the reply");
  if (!(llmMode ? readModelAnswer(r, current.model, *found) : readDetections(r, *found))) return;
  const float confidenceLimit = found->confidenceLimit;
  routing::Decision decision = routing::decide(found->items, found->count, confidenceLimit);
  String reason = describe(decision, confidenceLimit);
  if (found->tooMany) {
    decision.stream = routing::Stream::Other;
    reason = "more than " + String(MAX_DETECTIONS) + " detections";
  }
  const Destination& destination = settings::destinationFor(decision.stream);
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
  const ImuReading atBin = imuNow();
  moveServo(settings::homeAngle);
  checkTip(angle, atBin);
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
