// Camera interface. On the board it drives the OV2640 (camera_esp32.cpp); in
// the Wokwi simulator, which has no camera, it hands out the photos built in
// from sim/photos (camera_sim.cpp).
#pragma once

#include <cstddef>
#include <cstdint>

struct Photo {
  uint8_t* data = nullptr;  // JPEG bytes
  size_t length = 0;
  unsigned width = 0;
  unsigned height = 0;
  const char* name = nullptr;  // simulator photo name; nullptr on the board
  void* handle = nullptr;      // camera frame to give back
};

bool cameraBegin();
void cameraEnd();  // stops the camera; cameraBegin() starts it again
bool cameraTake(Photo& photo);
void cameraRelease(Photo& photo);

// A 640 x 480 photo shrunk to 80 x 60 grey pixels, for spotting changes on
// the plate. Always false in the simulator, which has no live camera.
constexpr int THUMB_PIXELS = 80 * 60;
bool cameraThumbnail(const Photo& photo, uint8_t* grey);  // THUMB_PIXELS bytes, 0-255 each

// JPEG quality 4-63, lower is better and bigger. The simulator's photos are
// made at build time, so there it only prints a note.
void cameraSetQuality(int quality);

// The sensor the camera driver found, such as "OV2640" or "OV3660".
const char* cameraModel();

// Simulator only; on the board these print a note and return false.
bool cameraListPhotos();
bool cameraChoosePhoto(int number);  // 1-based; that photo is sent next
