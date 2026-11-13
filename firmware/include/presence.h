// Whether something landed on the plate, from the camera and the IMU
// together (plate_watch.cpp), as plain C++ for the native unit tests.
//
// Asked once the camera sees nothing moving. With the IMU in use:
//   impact felt, any visible change      -> scan (white on white, if it hit hard)
//   no impact, most of the plate changed -> the light changed: watch the new view
//   no impact, some of the plate changed -> scan (an item too light to feel)
//   impact felt, nothing to see          -> a bump, once the camera has had time
// Without it, only the camera decides, as before the IMU.
#pragma once

#include <cstdint>

namespace presence {

enum class Verdict {
  Empty,     // nothing new: this view becomes the empty plate
  Scan,      // an item landed
  Lighting,  // the whole view changed but nothing landed: it becomes the empty plate
  Bump,      // the plate was jolted but looks empty: the impact is used up
};

struct Rules {
  float itemShare;     // changed share that is an item, by the camera alone
  float feltShare;     // changed share that is an item, with an impact felt
  float lightShare;    // changed share, with no impact, that is the light
  uint32_t bumpAfterMs;  // an impact this old with nothing to see is a bump
};

// changed: the share of the plate (0-1) that differs from the empty plate.
// felt: an impact that no verdict has used yet, feltAgeMs ago.
inline Verdict judge(float changed, bool imuInUse, bool felt, uint32_t feltAgeMs, const Rules& rules) {
  if (!imuInUse) return changed >= rules.itemShare ? Verdict::Scan : Verdict::Empty;
  if (felt && changed >= rules.feltShare) return Verdict::Scan;
  if (!felt && changed >= rules.lightShare) return Verdict::Lighting;
  if (changed >= rules.itemShare) return Verdict::Scan;
  if (felt && feltAgeMs >= rules.bumpAfterMs) return Verdict::Bump;
  return Verdict::Empty;
}

}  // namespace presence
