// Native tests for the LLM-mode request body: pio test -d firmware -e native
#include <unity.h>

#include <string>

#include "llm_request.h"

namespace {

std::string build() { return llm::requestJson("gpt-6-luna", "low", "high"); }

// The body with a stand-in for the photo, parsed back.
bool parse(JsonDocument& doc) {
  std::string json = build();
  const std::size_t mark = json.find(llm::kPhotoMark);
  if (mark == std::string::npos) return false;
  json.replace(mark, std::string(llm::kPhotoMark).size(), "AAAA");
  return !deserializeJson(doc, json);
}

void test_photo_mark_appears_once() {
  const std::string json = build();
  const std::size_t first = json.find(llm::kPhotoMark);
  TEST_ASSERT_TRUE(first != std::string::npos);
  TEST_ASSERT_TRUE(json.find(llm::kPhotoMark, first + 1) == std::string::npos);
  TEST_ASSERT_TRUE(json.find("\"data:image/jpeg;base64,@PHOTO@\"") != std::string::npos);
}

void test_body_is_the_request_the_backend_takes() {
  JsonDocument doc;
  TEST_ASSERT_TRUE(parse(doc));
  TEST_ASSERT_EQUAL_STRING("gpt-6-luna", doc["model"]);
  TEST_ASSERT_TRUE(doc["stream"].as<bool>());
  TEST_ASSERT_FALSE(doc["store"].as<bool>());
  TEST_ASSERT_EQUAL_STRING("low", doc["reasoning"]["effort"]);
  TEST_ASSERT_EQUAL_STRING(LLM_INSTRUCTIONS, doc["instructions"]);
  JsonObject image = doc["input"][0]["content"][0];
  TEST_ASSERT_EQUAL_STRING("message", doc["input"][0]["type"]);
  TEST_ASSERT_EQUAL_STRING("input_image", image["type"]);
  TEST_ASSERT_EQUAL_STRING("high", image["detail"]);
  TEST_ASSERT_EQUAL_STRING("data:image/jpeg;base64,AAAA", image["image_url"]);
}

void test_schema_is_embedded_as_json() {
  JsonDocument doc;
  TEST_ASSERT_TRUE(parse(doc));
  JsonObject format = doc["text"]["format"];
  TEST_ASSERT_EQUAL_STRING("json_schema", format["type"]);
  TEST_ASSERT_TRUE(format["strict"].as<bool>());
  JsonArray labels = format["schema"]["properties"]["items"]["items"]["properties"]["label"]["enum"];
  TEST_ASSERT_EQUAL(18, labels.size());
  TEST_ASSERT_EQUAL_STRING("paper", labels[0]);
  TEST_ASSERT_EQUAL_STRING("other", labels[17]);
}

}  // namespace

void setUp() {}
void tearDown() {}

int main() {
  UNITY_BEGIN();
  RUN_TEST(test_photo_mark_appears_once);
  RUN_TEST(test_body_is_the_request_the_backend_takes);
  RUN_TEST(test_schema_is_embedded_as_json);
  return UNITY_END();
}
