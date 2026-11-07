// Native tests for routing-v1: pio test -d firmware -e native
#include <unity.h>

#include "routing.h"

using routing::Decision;
using routing::Detection;
using routing::Reason;
using routing::Stream;

namespace {

constexpr double kLimit = 0.5;

Decision run(const Detection* items, std::size_t count) { return routing::decide(items, count, kLimit); }

void test_one_paper_goes_to_paper() {
  const Detection items[] = {{"paper", 0.9}};
  const Decision d = run(items, 1);
  TEST_ASSERT_TRUE(d.stream == Stream::Paper);
  TEST_ASSERT_TRUE(d.reason == Reason::OneStream);
}

void test_two_bottles_go_to_bottles() {
  const Detection items[] = {{"plastic_bottle", 0.9}, {"plastic_bottle", 0.7}};
  const Decision d = run(items, 2);
  TEST_ASSERT_TRUE(d.stream == Stream::PlasticBottles);
  TEST_ASSERT_TRUE(d.reason == Reason::OneStream);
}

void test_paper_and_bottle_go_to_other() {
  const Detection items[] = {{"paper", 0.9}, {"plastic_bottle", 0.9}};
  const Decision d = run(items, 2);
  TEST_ASSERT_TRUE(d.stream == Stream::Other);
  TEST_ASSERT_TRUE(d.reason == Reason::Mixed);
}

void test_paper_and_tissue_go_to_other() {
  const Detection items[] = {{"paper", 0.9}, {"tissue", 0.9}};
  TEST_ASSERT_TRUE(run(items, 2).reason == Reason::Mixed);
}

void test_items_that_all_go_to_other_go_to_other() {
  const Detection items[] = {{"tissue", 0.9}, {"food_wrapper", 0.8}, {"paper_cup", 0.6}};
  const Decision d = run(items, 3);
  TEST_ASSERT_TRUE(d.stream == Stream::Other);
  TEST_ASSERT_TRUE(d.reason == Reason::OneStream);
}

void test_nothing_detected_goes_to_other() {
  const Decision d = run(nullptr, 0);
  TEST_ASSERT_TRUE(d.stream == Stream::Other);
  TEST_ASSERT_TRUE(d.reason == Reason::NothingDetected);
}

void test_low_confidence_item_sends_the_plate_to_other() {
  const Detection items[] = {{"paper", 0.9}, {"paper", 0.49}};
  const Decision d = run(items, 2);
  TEST_ASSERT_TRUE(d.stream == Stream::Other);
  TEST_ASSERT_TRUE(d.reason == Reason::LowConfidence);
  TEST_ASSERT_EQUAL_PTR(items[1].label, d.label);
}

void test_confidence_at_the_limit_counts() {
  const Detection items[] = {{"paper", 0.5}};
  TEST_ASSERT_TRUE(run(items, 1).stream == Stream::Paper);
}

void test_label_outside_v4_goes_to_other() {
  const Detection items[] = {{"bottle", 0.95}};
  const Decision d = run(items, 1);
  TEST_ASSERT_TRUE(d.stream == Stream::Other);
  TEST_ASSERT_TRUE(d.reason == Reason::UnknownLabel);
  TEST_ASSERT_EQUAL_STRING("bottle", d.label);
}

void test_every_v4_class_has_a_route() {
  const char* classes[] = {"paper", "plastic_bottle", "paper_cup", "plastic_container",
                           "plastic_cutlery", "tissue", "food_wrapper"};
  for (const char* name : classes) {
    Stream stream;
    TEST_ASSERT_TRUE_MESSAGE(routing::streamForLabel(name, stream), name);
  }
}

}  // namespace

void setUp() {}
void tearDown() {}

int main() {
  UNITY_BEGIN();
  RUN_TEST(test_one_paper_goes_to_paper);
  RUN_TEST(test_two_bottles_go_to_bottles);
  RUN_TEST(test_paper_and_bottle_go_to_other);
  RUN_TEST(test_paper_and_tissue_go_to_other);
  RUN_TEST(test_items_that_all_go_to_other_go_to_other);
  RUN_TEST(test_nothing_detected_goes_to_other);
  RUN_TEST(test_low_confidence_item_sends_the_plate_to_other);
  RUN_TEST(test_confidence_at_the_limit_counts);
  RUN_TEST(test_label_outside_v4_goes_to_other);
  RUN_TEST(test_every_v4_class_has_a_route);
  return UNITY_END();
}
