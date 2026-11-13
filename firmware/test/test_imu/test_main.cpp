// Native tests for the IMU's arithmetic (imu_math.h) and the camera-and-IMU
// rules (presence.h): pio test -d firmware -e native
#include <unity.h>

#include "imu_math.h"
#include "presence.h"

using imu::Sample;
using imu::Tracker;
using imu::Vec3;
using presence::Verdict;

namespace {

constexpr uint32_t kStepMs = 5;  // 200 samples a second

Sample at(Vec3 accel) {
  Sample s;
  s.accelG = accel;
  return s;
}

const Vec3 kFlat = {0, 0, 1};

// Feeds the same acceleration for durationMs; returns the impacts it started.
int feed(Tracker& t, uint32_t& nowMs, Vec3 accel, uint32_t durationMs, bool countImpacts = true) {
  int impacts = 0;
  for (uint32_t end = nowMs + durationMs; nowMs < end; nowMs += kStepMs) impacts += t.update(at(accel), nowMs, countImpacts);
  return impacts;
}

// A landing: the plate jolts for 15 ms.
int jolt(Tracker& t, uint32_t& nowMs, float g, bool countImpacts = true) {
  return feed(t, nowMs, {0, 0, 1 + g}, 15, countImpacts);
}

void test_decode_reads_big_endian_counts() {
  // accel x +1 g, y -1 g, z +0.5 g at 8192 counts a g; temperature 0 counts;
  // gyro x 131 counts (2 deg/s at 65.5 a deg/s), y 0, z -66 counts (about -1)
  const uint8_t raw[14] = {0x20, 0x00, 0xE0, 0x00, 0x10, 0x00, 0x00, 0x00, 0x00, 0x83, 0x00, 0x00, 0xFF, 0xBE};
  const Sample s = imu::decode(raw, 8192, 65.5f);
  TEST_ASSERT_FLOAT_WITHIN(1e-4, 1.0f, s.accelG.x);
  TEST_ASSERT_FLOAT_WITHIN(1e-4, -1.0f, s.accelG.y);
  TEST_ASSERT_FLOAT_WITHIN(1e-4, 0.5f, s.accelG.z);
  TEST_ASSERT_FLOAT_WITHIN(1e-3, 36.53f, s.temperatureC);
  TEST_ASSERT_FLOAT_WITHIN(1e-3, 2.0f, s.gyroDps.x);
  TEST_ASSERT_FLOAT_WITHIN(1e-3, 0.0f, s.gyroDps.y);
  TEST_ASSERT_FLOAT_WITHIN(1e-2, -1.0f, s.gyroDps.z);
}

void test_flat_chip_reads_level_either_side_up() {
  TEST_ASSERT_FLOAT_WITHIN(1e-3, 0, imu::tiltDegrees({0, 0, 1}, {}, false));
  TEST_ASSERT_FLOAT_WITHIN(1e-3, 0, imu::tiltDegrees({0, 0, -1}, {}, false));
}

void test_tilt_from_flat() {
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 45, imu::tiltDegrees({0.70711f, 0, 0.70711f}, {}, false));
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 30, imu::tiltDegrees({0, 0.5f, -0.86603f}, {}, false));
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 90, imu::tiltDegrees({1, 0, 0}, {}, false));
}

void test_tilt_from_a_saved_level_ignores_how_the_chip_sits() {
  // Mounted at an angle: level reads 20 degrees off the chip's Z axis.
  const Vec3 level = {0.34202f, 0, 0.93969f};
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 0, imu::tiltDegrees(level, level, true));
  // The plate tips 25 degrees further the same way: 45 off the chip's Z.
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 25, imu::tiltDegrees({0.70711f, 0, 0.70711f}, level, true));
  // Readings in counts of a different size still give the same angle.
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 25, imu::tiltDegrees({1.41421f, 0, 1.41421f}, level, true));
}

void test_no_reading_has_no_tilt() {
  TEST_ASSERT_EQUAL_FLOAT(0, imu::tiltDegrees({0, 0, 0}, {}, false));
  TEST_ASSERT_EQUAL_FLOAT(0, imu::tiltDegrees({0, 0, 1}, {0, 0, 0}, true));
}

void test_resting_plate_is_still_with_no_impacts() {
  Tracker t;
  uint32_t now = 0;
  TEST_ASSERT_EQUAL(0, feed(t, now, kFlat, 2000));
  TEST_ASSERT_TRUE(t.still());
  TEST_ASSERT_TRUE(t.stillForMs(now) >= 1900);
  TEST_ASSERT_FLOAT_WITHIN(0.001f, 0, t.shakeG());
}

void test_one_landing_counts_once() {
  Tracker t;
  uint32_t now = 0;
  feed(t, now, kFlat, 1000);
  TEST_ASSERT_EQUAL(1, jolt(t, now, 0.5f));
  TEST_ASSERT_FALSE(t.still());
  feed(t, now, kFlat, 1000);
  TEST_ASSERT_EQUAL(1u, t.impacts());
  TEST_ASSERT_TRUE(t.lastImpactPeakG() > 0.3f);
  TEST_ASSERT_TRUE(t.still());
}

void test_bounces_count_as_the_same_landing() {
  Tracker t;
  uint32_t now = 0;
  feed(t, now, kFlat, 1000);
  int impacts = jolt(t, now, 0.5f);
  impacts += feed(t, now, kFlat, 60);
  impacts += jolt(t, now, 0.3f);  // a bounce 75 ms later
  impacts += feed(t, now, kFlat, 1000);
  TEST_ASSERT_EQUAL(1, impacts);
}

void test_two_landings_count_twice() {
  Tracker t;
  uint32_t now = 0;
  feed(t, now, kFlat, 1000);
  int impacts = jolt(t, now, 0.5f);
  impacts += feed(t, now, kFlat, 1000);
  impacts += jolt(t, now, 0.5f);
  TEST_ASSERT_EQUAL(2, impacts);
}

void test_a_jolt_below_the_threshold_is_not_an_impact() {
  Tracker t;
  uint32_t now = 0;
  feed(t, now, kFlat, 1000);
  TEST_ASSERT_EQUAL(0, jolt(t, now, 0.05f));
}

void test_the_servos_own_jolts_never_count() {
  Tracker t;
  uint32_t now = 0;
  feed(t, now, kFlat, 1000);
  TEST_ASSERT_EQUAL(0, jolt(t, now, 0.8f, false));
  // Counting again while the shake from that jolt dies down: still nothing.
  TEST_ASSERT_EQUAL(0, feed(t, now, kFlat, 1000));
  TEST_ASSERT_EQUAL(0u, t.impacts());
}

void test_a_lasting_step_counts_once() {
  // The simulator's sliders change the reading in one step and leave it.
  Tracker t;
  uint32_t now = 0;
  feed(t, now, kFlat, 1000);
  TEST_ASSERT_EQUAL(1, feed(t, now, {0.3f, 0, 0.95f}, 3000));
  TEST_ASSERT_TRUE(t.still());
}

void test_gravity_follows_a_tip() {
  Tracker t;
  uint32_t now = 0;
  feed(t, now, kFlat, 1000);
  feed(t, now, {0.70711f, 0, 0.70711f}, 1000, false);
  TEST_ASSERT_FLOAT_WITHIN(0.5f, 45, imu::tiltDegrees(t.gravity(), {}, false));
}

void test_rotation_reads_without_the_gyros_zero() {
  Tracker t;
  uint32_t now = 0;
  feed(t, now, kFlat, 100);  // starts out reading 0
  Sample s = at(kFlat);
  s.gyroDps = {1.5f, -0.5f, 0.2f};  // the gyro's own zero error, at rest
  t.update(s, now, true);
  TEST_ASSERT_TRUE(t.rotationDps() > 1.5f);
  for (int i = 0; i < 2000; ++i, now += kStepMs) t.update(s, now, true);
  TEST_ASSERT_FLOAT_WITHIN(0.05f, 0, t.rotationDps());
}

constexpr presence::Rules kRules = {0.01f, 0.002f, 0.8f, 1000};

void test_without_the_imu_only_the_camera_decides() {
  TEST_ASSERT_TRUE(presence::judge(0.02f, false, false, 0, kRules) == Verdict::Scan);
  TEST_ASSERT_TRUE(presence::judge(0.005f, false, true, 5000, kRules) == Verdict::Empty);
  TEST_ASSERT_TRUE(presence::judge(0.9f, false, false, 0, kRules) == Verdict::Scan);
}

void test_an_impact_lowers_what_counts_as_an_item() {
  TEST_ASSERT_TRUE(presence::judge(0.004f, true, true, 300, kRules) == Verdict::Scan);
  TEST_ASSERT_TRUE(presence::judge(0.004f, true, false, 0, kRules) == Verdict::Empty);
}

void test_a_big_change_with_no_impact_is_the_light() {
  TEST_ASSERT_TRUE(presence::judge(0.9f, true, false, 0, kRules) == Verdict::Lighting);
  TEST_ASSERT_TRUE(presence::judge(0.9f, true, true, 300, kRules) == Verdict::Scan);
}

void test_a_light_item_with_no_impact_still_scans() {
  TEST_ASSERT_TRUE(presence::judge(0.03f, true, false, 0, kRules) == Verdict::Scan);
}

void test_an_impact_with_nothing_to_see_is_a_bump_only_once_the_camera_had_time() {
  TEST_ASSERT_TRUE(presence::judge(0.0005f, true, true, 300, kRules) == Verdict::Empty);
  TEST_ASSERT_TRUE(presence::judge(0.0005f, true, true, 1500, kRules) == Verdict::Bump);
}

}  // namespace

void setUp() {}
void tearDown() {}

int main() {
  UNITY_BEGIN();
  RUN_TEST(test_decode_reads_big_endian_counts);
  RUN_TEST(test_flat_chip_reads_level_either_side_up);
  RUN_TEST(test_tilt_from_flat);
  RUN_TEST(test_tilt_from_a_saved_level_ignores_how_the_chip_sits);
  RUN_TEST(test_no_reading_has_no_tilt);
  RUN_TEST(test_resting_plate_is_still_with_no_impacts);
  RUN_TEST(test_one_landing_counts_once);
  RUN_TEST(test_bounces_count_as_the_same_landing);
  RUN_TEST(test_two_landings_count_twice);
  RUN_TEST(test_a_jolt_below_the_threshold_is_not_an_impact);
  RUN_TEST(test_the_servos_own_jolts_never_count);
  RUN_TEST(test_a_lasting_step_counts_once);
  RUN_TEST(test_gravity_follows_a_tip);
  RUN_TEST(test_rotation_reads_without_the_gyros_zero);
  RUN_TEST(test_without_the_imu_only_the_camera_decides);
  RUN_TEST(test_an_impact_lowers_what_counts_as_an_item);
  RUN_TEST(test_a_big_change_with_no_impact_is_the_light);
  RUN_TEST(test_a_light_item_with_no_impact_still_scans);
  RUN_TEST(test_an_impact_with_nothing_to_see_is_a_bump_only_once_the_camera_had_time);
  return UNITY_END();
}
