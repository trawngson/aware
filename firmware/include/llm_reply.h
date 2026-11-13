// Reads the model's answer out of an LLM-mode reply. The ChatGPT Codex
// backend only streams: the reply is server-sent events, one "data: {json}"
// line each, and the answer is the text of the response.output_text.done
// event, shaped by LLM_SCHEMA ({"items": [{"label": ...}]}). Plain C++ and
// ArduinoJson, so the native tests run it on the Mac.
#pragma once

#include <ArduinoJson.h>

#include <cstddef>
#include <cstring>
#include <string>

namespace llm {

constexpr std::size_t kMaxItems = 32;
constexpr std::size_t kMaxLabel = 32;

struct Answer {
  bool ok = false;
  std::string error;      // why there is no answer, when !ok
  std::size_t count = 0;  // items on the plate, up to kMaxItems
  bool tooMany = false;   // the model listed more than kMaxItems
  char labels[kMaxItems][kMaxLabel] = {};
};

namespace detail {

inline bool startsWith(const char* text, std::size_t length, const char* prefix) {
  const std::size_t n = std::strlen(prefix);
  return length >= n && std::memcmp(text, prefix, n) == 0;
}

inline bool contains(const char* text, std::size_t length, const char* needle) {
  const std::size_t n = std::strlen(needle);
  for (std::size_t i = 0; n <= length && i <= length - n; ++i) {
    if (std::memcmp(text + i, needle, n) == 0) return true;
  }
  return false;
}

// The items list in the answer text.
inline bool readItems(const char* text, Answer& answer) {
  JsonDocument doc;
  if (deserializeJson(doc, text)) {
    answer.error = std::string("the answer is not JSON: ") + std::string(text).substr(0, 120);
    return false;
  }
  JsonArrayConst items = doc["items"].as<JsonArrayConst>();
  if (items.isNull()) {
    answer.error = std::string("the answer has no items list: ") + std::string(text).substr(0, 120);
    return false;
  }
  for (JsonVariantConst item : items) {
    const char* label = item["label"] | "";
    if (answer.count == kMaxItems) {
      answer.tooMany = true;
      break;
    }
    std::strncpy(answer.labels[answer.count], label, kMaxLabel - 1);
    answer.labels[answer.count][kMaxLabel - 1] = '\0';
    ++answer.count;
  }
  return true;
}

// The message in a response.failed, response.incomplete or error event.
inline std::string failure(JsonDocument& event) {
  const char* type = event["type"] | "";
  const char* message = event["response"]["error"]["message"] | static_cast<const char*>(nullptr);
  if (!message) message = event["error"]["message"] | static_cast<const char*>(nullptr);
  if (!message) message = event["message"] | static_cast<const char*>(nullptr);
  if (!message) message = event["response"]["incomplete_details"]["reason"] | "no reason given";
  return std::string(type) + ": " + message;
}

}  // namespace detail

// The answer in a 200 reply's events.
inline Answer readAnswer(const char* body, std::size_t length) {
  Answer answer;
  std::size_t start = 0;
  while (start < length) {
    std::size_t end = start;
    while (end < length && body[end] != '\n') ++end;
    const char* line = body + start;
    std::size_t lineLength = end - start;
    start = end + 1;
    if (lineLength && line[lineLength - 1] == '\r') --lineLength;
    if (!detail::startsWith(line, lineLength, "data:")) continue;
    line += 5;
    lineLength -= 5;
    if (lineLength && line[0] == ' ') ++line, --lineLength;

    // Only a few events matter; skip the rest (mostly one-token deltas)
    // without parsing them. An "error" key is in a few others too, as null.
    const bool done = detail::contains(line, lineLength, "\"response.output_text.done\"");
    const bool failed = detail::contains(line, lineLength, "\"response.failed\"") ||
                        detail::contains(line, lineLength, "\"response.incomplete\"") ||
                        detail::contains(line, lineLength, "\"error\"");
    if (!done && !failed) continue;
    JsonDocument event;
    if (deserializeJson(event, line, lineLength)) continue;
    const char* type = event["type"] | "";
    if (done && std::strcmp(type, "response.output_text.done") == 0) {
      answer.ok = detail::readItems(event["text"] | "", answer);
      return answer;
    }
    if (std::strcmp(type, "response.failed") == 0 || std::strcmp(type, "response.incomplete") == 0 ||
        std::strcmp(type, "error") == 0) {
      answer.error = detail::failure(event);
      return answer;
    }
  }
  answer.error = "the reply ended without an answer";
  return answer;
}

// What a refused request (not 200) says, for the log: {"detail": ...} or
// {"error": {"message": ...}}, else the start of the body.
inline std::string errorText(const char* body, std::size_t length) {
  JsonDocument doc;
  if (!deserializeJson(doc, body, length)) {
    if (doc["detail"].is<const char*>()) return doc["detail"].as<const char*>();
    if (doc["error"]["message"].is<const char*>()) return doc["error"]["message"].as<const char*>();
  }
  return std::string(body, length < 160 ? length : 160);
}

}  // namespace llm
