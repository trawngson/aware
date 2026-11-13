// One scan: the board photographs the plate, sends the JPEG to the detection
// server (or, in LLM mode, to an OpenAI model; llm.h), routes the items with
// the routing-v1 rules, and turns the servo to that stream's angle. It holds
// there, then returns home. On any failure it holds: the LED turns red, a
// [hold] line says why, and the servo stays home. Worker only.
#pragma once

#include "camera.h"

void runScan();

// "snap": a photo for the viewer, without the server.
void snap();

// Sends the photo to scripts/viewer.py on the Mac as base64 text, between the
// control bytes STX and ETX, with "-----BEGIN JPEG <bytes>-----" and
// "-----END JPEG-----" inside ("JPEG" for a scan or snap, "LIVE" for a frame
// of the live view). The monitor's aware_feed filter takes everything from STX
// to ETX out of the terminal, wherever it comes, so the prompt line is left
// as it is. About 0.15 s for 30 KB at 2 Mbit/s. The other tasks wait to print
// until it ends, so nothing lands inside it.
void sendPhoto(const Photo& photo, const char* kind = "JPEG");

// Gives the camera frame back however the function that took it returns.
struct HeldPhoto {
  Photo photo;
  ~HeldPhoto() { cameraRelease(photo); }
};
