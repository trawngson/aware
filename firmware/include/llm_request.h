// The JSON body of an LLM-mode request (llm.h), with kPhotoMark where the
// photo goes. The board writes the photo's base64 there straight into the
// request buffer instead of copying it into the JSON. Plain C++ and
// ArduinoJson, so the native tests check it on the Mac.
#pragma once

#include <ArduinoJson.h>

#include <string>

#include "llm_prompt.h"

namespace llm {

constexpr const char* kPhotoMark = "@PHOTO@";

// Empty when out of memory.
inline std::string requestJson(const char* model, const char* effort, const char* detail) {
  JsonDocument doc;
  doc["model"] = model;
  doc["instructions"] = LLM_INSTRUCTIONS;
  doc["store"] = false;
  doc["stream"] = true;  // the backend refuses anything else
  doc["reasoning"]["effort"] = effort;
  JsonObject format = doc["text"]["format"].to<JsonObject>();
  format["type"] = "json_schema";
  format["name"] = "bin_items";
  format["strict"] = true;
  format["schema"] = serialized(LLM_SCHEMA);
  JsonObject message = doc["input"].to<JsonArray>().add<JsonObject>();
  message["type"] = "message";
  message["role"] = "user";
  JsonObject image = message["content"].to<JsonArray>().add<JsonObject>();
  image["type"] = "input_image";
  image["detail"] = detail;
  image["image_url"] = std::string("data:image/jpeg;base64,") + kPhotoMark;
  std::string json;
  serializeJson(doc, json);
  if (doc.overflowed() || json.find(kPhotoMark) == std::string::npos) return std::string();
  return json;
}

}  // namespace llm
