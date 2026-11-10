// Native tests for reading LLM-mode replies: pio test -d firmware -e native
// The replies follow the event stream the ChatGPT Codex backend sent on
// 2026-11-07 (event names, field names, LF line ends), with most fields cut.
#include <unity.h>

#include <cstring>
#include <string>

#include "llm_reply.h"
#include "routing.h"

namespace {

llm::Answer read(const std::string& body) { return llm::readAnswer(body.c_str(), body.size()); }

// A whole stream whose answer is the given JSON text (already escaped).
std::string stream(const char* escapedAnswer) {
  return std::string(
             "event: response.created\n"
             "data: {\"type\":\"response.created\",\"sequence_number\":0,\"response\":{\"id\":\"resp_1\","
             "\"status\":\"in_progress\",\"error\":null,\"instructions\":\"You sort waste\",\"output\":[]}}\n\n"
             "event: response.output_text.delta\n"
             "data: {\"type\":\"response.output_text.delta\",\"sequence_number\":4,\"item_id\":\"msg_1\","
             "\"delta\":\"{\\\"\",\"logprobs\":[],\"obfuscation\":\"ab\"}\n\n"
             "event: response.output_text.done\n"
             "data: {\"type\":\"response.output_text.done\",\"sequence_number\":20,\"item_id\":\"msg_1\","
             "\"text\":\"") +
         escapedAnswer +
         "\",\"logprobs\":[]}\n\n"
         "event: response.completed\n"
         "data: {\"type\":\"response.completed\",\"sequence_number\":23,\"response\":{\"id\":\"resp_1\","
         "\"status\":\"completed\",\"error\":null,\"output\":[]}}\n\n";
}

routing::Decision route(const llm::Answer& answer) {
  routing::Detection items[llm::kMaxItems];
  for (std::size_t i = 0; i < answer.count; ++i) items[i] = {answer.labels[i], 1.0};
  return routing::decide(items, answer.count, 0.0);
}

void test_two_papers_are_read_and_go_to_paper() {
  const llm::Answer a = read(stream("{\\\"items\\\":[{\\\"label\\\":\\\"paper\\\"},{\\\"label\\\":\\\"paper\\\"}]}"));
  TEST_ASSERT_TRUE(a.ok);
  TEST_ASSERT_EQUAL(2, a.count);
  TEST_ASSERT_EQUAL_STRING("paper", a.labels[0]);
  TEST_ASSERT_TRUE(route(a).stream == routing::Stream::Paper);
}

void test_cup_and_bottle_go_to_other() {
  const llm::Answer a =
      read(stream("{\\\"items\\\":[{\\\"label\\\":\\\"plastic_bottle\\\"},{\\\"label\\\":\\\"paper_cup\\\"}]}"));
  TEST_ASSERT_TRUE(a.ok);
  TEST_ASSERT_TRUE(route(a).reason == routing::Reason::Mixed);
}

void test_empty_plate_goes_to_other() {
  const llm::Answer a = read(stream("{\\\"items\\\":[]}"));
  TEST_ASSERT_TRUE(a.ok);
  TEST_ASSERT_EQUAL(0, a.count);
  TEST_ASSERT_TRUE(route(a).reason == routing::Reason::NothingDetected);
}

void test_other_label_goes_to_other() {
  const llm::Answer a = read(stream("{\\\"items\\\":[{\\\"label\\\":\\\"other\\\"}]}"));
  TEST_ASSERT_TRUE(a.ok);
  TEST_ASSERT_TRUE(route(a).reason == routing::Reason::UnknownLabel);
}

void test_named_non_bin_items_go_to_other() {
  const llm::Answer a =
      read(stream("{\\\"items\\\":[{\\\"label\\\":\\\"drink_carton\\\"},{\\\"label\\\":\\\"hazard\\\"}]}"));
  TEST_ASSERT_TRUE(a.ok);
  TEST_ASSERT_EQUAL(2, a.count);
  TEST_ASSERT_TRUE(route(a).stream == routing::Stream::Other);
  TEST_ASSERT_TRUE(route(a).reason == routing::Reason::UnknownLabel);
}

void test_crlf_line_ends_are_read() {
  std::string body = stream("{\\\"items\\\":[{\\\"label\\\":\\\"tissue\\\"}]}");
  std::string crlf;
  for (char c : body) {
    if (c == '\n') crlf += '\r';
    crlf += c;
  }
  const llm::Answer a = read(crlf);
  TEST_ASSERT_TRUE(a.ok);
  TEST_ASSERT_EQUAL_STRING("tissue", a.labels[0]);
}

void test_more_items_than_fit_are_flagged() {
  std::string answer = "{\\\"items\\\":[";
  for (std::size_t i = 0; i < llm::kMaxItems + 3; ++i) answer += std::string(i ? "," : "") + "{\\\"label\\\":\\\"paper\\\"}";
  answer += "]}";
  const llm::Answer a = read(stream(answer.c_str()));
  TEST_ASSERT_TRUE(a.ok);
  TEST_ASSERT_TRUE(a.tooMany);
  TEST_ASSERT_EQUAL(llm::kMaxItems, a.count);
}

void test_long_label_is_cut_not_overflowed() {
  const llm::Answer a =
      read(stream("{\\\"items\\\":[{\\\"label\\\":\\\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\\\"}]}"));
  TEST_ASSERT_TRUE(a.ok);
  TEST_ASSERT_EQUAL(llm::kMaxLabel - 1, std::strlen(a.labels[0]));
}

void test_failed_response_gives_its_message() {
  const llm::Answer a = read(
      "event: response.failed\n"
      "data: {\"type\":\"response.failed\",\"response\":{\"status\":\"failed\","
      "\"error\":{\"code\":\"server_error\",\"message\":\"The model is overloaded\"}}}\n\n");
  TEST_ASSERT_FALSE(a.ok);
  TEST_ASSERT_TRUE(a.error.find("The model is overloaded") != std::string::npos);
}

void test_error_event_gives_its_message() {
  const llm::Answer a = read("event: error\ndata: {\"type\": \"error\", \"message\": \"usage limit\"}\n\n");
  TEST_ASSERT_FALSE(a.ok);
  TEST_ASSERT_TRUE(a.error.find("usage limit") != std::string::npos);
}

void test_stream_cut_before_the_answer_is_an_error() {
  std::string body = stream("{\\\"items\\\":[]}");
  body = body.substr(0, body.find("event: response.output_text.done"));
  const llm::Answer a = read(body);
  TEST_ASSERT_FALSE(a.ok);
  TEST_ASSERT_EQUAL_STRING("the reply ended without an answer", a.error.c_str());
}

void test_answer_that_is_not_the_schema_is_an_error() {
  const llm::Answer a = read(stream("paper"));
  TEST_ASSERT_FALSE(a.ok);
}

void test_refusal_text_is_read() {
  const std::string detail = "{\"detail\":\"Stream must be set to true\"}";
  TEST_ASSERT_EQUAL_STRING("Stream must be set to true", llm::errorText(detail.c_str(), detail.size()).c_str());
  const std::string error = "{\"error\":{\"message\":\"Unsupported value\",\"type\":\"invalid_request_error\"}}";
  TEST_ASSERT_EQUAL_STRING("Unsupported value", llm::errorText(error.c_str(), error.size()).c_str());
  const std::string html = "<html>blocked</html>";
  TEST_ASSERT_EQUAL_STRING("<html>blocked</html>", llm::errorText(html.c_str(), html.size()).c_str());
}

}  // namespace

void setUp() {}
void tearDown() {}

int main() {
  UNITY_BEGIN();
  RUN_TEST(test_two_papers_are_read_and_go_to_paper);
  RUN_TEST(test_cup_and_bottle_go_to_other);
  RUN_TEST(test_empty_plate_goes_to_other);
  RUN_TEST(test_other_label_goes_to_other);
  RUN_TEST(test_named_non_bin_items_go_to_other);
  RUN_TEST(test_crlf_line_ends_are_read);
  RUN_TEST(test_more_items_than_fit_are_flagged);
  RUN_TEST(test_long_label_is_cut_not_overflowed);
  RUN_TEST(test_failed_response_gives_its_message);
  RUN_TEST(test_error_event_gives_its_message);
  RUN_TEST(test_stream_cut_before_the_answer_is_an_error);
  RUN_TEST(test_answer_that_is_not_the_schema_is_an_error);
  RUN_TEST(test_refusal_text_is_read);
  return UNITY_END();
}
