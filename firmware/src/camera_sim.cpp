// Simulator camera: Wokwi has no camera, so each scan sends the next photo
// from sim/photos. scripts/sim_photos.py shrinks them to at most 640 px and
// builds them into sim/generated/sim_photos.h.
#ifdef AWARE_SIMULATOR

#include <Arduino.h>

#include "camera.h"
#include "sim_photos.h"

namespace {
unsigned nextPhoto = 0;
}

bool cameraBegin() {
  if (kSimPhotoCount == 0) {
    Serial.println("[camera] simulator: no photos. Put JPEG, PNG or HEIC files in sim/photos and rebuild.");
    return false;
  }
  Serial.printf("[camera] simulator: %u photos from sim/photos, sent in turn. Type  photos  to list them.\n",
                kSimPhotoCount);
  return true;
}

bool cameraTake(Photo& photo) {
  if (kSimPhotoCount == 0) return false;
  const SimPhoto& p = kSimPhotos[nextPhoto];
  nextPhoto = (nextPhoto + 1) % kSimPhotoCount;
  photo.data = const_cast<uint8_t*>(p.data);
  photo.length = p.length;
  photo.width = p.width;
  photo.height = p.height;
  photo.name = p.name;
  photo.handle = nullptr;
  return true;
}

void cameraRelease(Photo& photo) { photo = Photo(); }

bool cameraThumbnail(uint8_t*) { return false; }

void cameraSetQuality(int) {
  Serial.println("The simulator's photos are made at build time; quality applies on the board.");
}

bool cameraListPhotos() {
  for (unsigned i = 0; i < kSimPhotoCount; ++i) {
    Serial.printf("%s %u. %s (%ux%u, %u KB)\n", i == nextPhoto ? "next" : "    ", i + 1, kSimPhotos[i].name,
                  kSimPhotos[i].width, kSimPhotos[i].height, kSimPhotos[i].length / 1024);
  }
  return true;
}

bool cameraChoosePhoto(int number) {
  if (number < 1 || static_cast<unsigned>(number) > kSimPhotoCount) {
    Serial.printf("Choose a photo from 1 to %u. Type  photos  to list them.\n", kSimPhotoCount);
    return false;
  }
  nextPhoto = static_cast<unsigned>(number - 1);
  Serial.printf("Next scan sends %s\n", kSimPhotos[nextPhoto].name);
  return true;
}

#endif  // AWARE_SIMULATOR
