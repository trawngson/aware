// routing-v1 (backend/physical_bin/routing-v1.yaml, approved 2026-10-17) as
// plain C++, so it runs on the board and in the native unit tests.
#pragma once

#include <cstddef>
#include <cstring>

namespace routing {

enum class Stream { Paper, PlasticBottles, Other };

enum class Reason {
  OneStream,        // every item belongs to the chosen stream
  NothingDetected,  // the plate was scanned but nothing came back
  LowConfidence,    // `label` is below the confidence limit
  UnknownLabel,     // `label` is not an ontology v4 class
  Mixed,            // the items belong to more than one stream
};

struct Detection {
  const char* label;
  double confidence;
};

struct Decision {
  Stream stream;
  Reason reason;
  const char* label;  // the item behind LowConfidence or UnknownLabel
};

struct ClassRoute {
  const char* label;
  Stream stream;
};

// Ontology v4 class -> stream.
constexpr ClassRoute kClassRoutes[] = {
    {"paper", Stream::Paper},
    {"plastic_bottle", Stream::PlasticBottles},
    {"paper_cup", Stream::Other},
    {"plastic_container", Stream::Other},
    {"plastic_cutlery", Stream::Other},
    {"tissue", Stream::Other},
    {"food_wrapper", Stream::Other},
};

inline const char* streamName(Stream stream) {
  switch (stream) {
    case Stream::Paper:
      return "paper";
    case Stream::PlasticBottles:
      return "plastic_bottles";
    default:
      return "other";
  }
}

inline bool streamForLabel(const char* label, Stream& stream) {
  for (const auto& route : kClassRoutes) {
    if (std::strcmp(route.label, label) == 0) {
      stream = route.stream;
      return true;
    }
  }
  return false;
}

// When every item belongs to one stream, the plate goes there. Nothing
// detected, a low-confidence item, a label outside v4, or items for more
// than one stream send it to other.
inline Decision decide(const Detection* items, std::size_t count, double minConfidence) {
  if (count == 0) return {Stream::Other, Reason::NothingDetected, nullptr};
  for (std::size_t i = 0; i < count; ++i) {
    if (items[i].confidence < minConfidence) return {Stream::Other, Reason::LowConfidence, items[i].label};
  }
  Stream chosen = Stream::Other;
  for (std::size_t i = 0; i < count; ++i) {
    Stream stream;
    if (!streamForLabel(items[i].label, stream)) return {Stream::Other, Reason::UnknownLabel, items[i].label};
    if (i == 0) {
      chosen = stream;
    } else if (stream != chosen) {
      return {Stream::Other, Reason::Mixed, nullptr};
    }
  }
  return {chosen, Reason::OneStream, nullptr};
}

}  // namespace routing
