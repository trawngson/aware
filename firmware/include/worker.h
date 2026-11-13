// The worker task owns the camera, the servo and the LED. It runs the jobs
// the console hands it ("scan", "snap", "servo", "angle", "camera") one at a
// time, in the order they came, and between them looks at the plate
// (plate_watch.h).
#pragma once

#include <Arduino.h>

#include <atomic>

enum class Job : uint8_t { Scan, Snap, Servo, ShowAngle, CameraOff, CameraOn };

struct Work {
  Job job;
  int angle;  // Servo and ShowAngle
};

// What the worker is doing, for the console's messages and "status".
enum class Activity : uint8_t { Free, Scanning, Photo, Servo, Angle };
Activity workerActivity();
const char* activityText(Activity activity);
unsigned waitingJobs();

// Set by startCamera() and "camera off". The console reads it for "status".
extern std::atomic<bool> cameraReady;

// Starts the camera with the saved JPEG quality: in setup(), before the
// worker runs, and then for "camera on".
void startCamera();

// Starts the worker task. Call at the end of setup().
void workerBegin();

// Hands a camera or servo job to the worker, and says so when it has to wait.
// False, with a [busy] line, when too many are already waiting. Console only.
bool queueWork(const Work& work, const String& what);

// A scan for "scan" or the BOOT button. False, with a [busy] line, when a scan
// is already running or waiting, so an item is never tipped twice.
bool requestScan();
