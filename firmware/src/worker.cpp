#include "worker.h"

#include "camera.h"
#include "config.h"
#include "console.h"
#include "imu.h"
#include "plate_watch.h"
#include "scan.h"
#include "servo.h"
#include "settings.h"
#include "status_led.h"

std::atomic<bool> cameraReady{false};

namespace {

QueueHandle_t workQueue = nullptr;

const char* const kActivityText[] = {"free", "scanning", "taking a photo", "turning the servo", "showing an angle"};
std::atomic<Activity> activity{Activity::Free};
// A scan is waiting in the queue; another "scan" or BOOT press is skipped.
std::atomic<bool> scanQueued{false};

struct Busy {
  explicit Busy(Activity what) { activity = what; }
  ~Busy() { activity = Activity::Free; }
};

void doWork(const Work& work) {
  switch (work.job) {
    case Job::Scan: {
      Busy busy(Activity::Scanning);
      scanQueued = false;
      runScan();
      break;
    }
    case Job::Snap: {
      Busy busy(Activity::Photo);
      snap();
      break;
    }
    case Job::Servo: {
      Busy busy(Activity::Servo);
      moveServo(work.angle);
      imuReportTilt();
      break;
    }
    case Job::CameraOff:
      if (cameraReady) {
        cameraReady = false;
        cameraEnd();
      }
      say("[camera] off: no automatic scans or live view until \"camera on\"\n");
      break;
    case Job::CameraOn:
      if (!cameraReady) startCamera();
      break;
    case Job::ShowAngle: {
      Busy busy(Activity::Angle);
      visit(work.angle);
      break;
    }
  }
}

// Runs queued jobs in order; between them, looks at the plate.
void workerTask(void*) {
  for (;;) {
    ledUpdate();
    Work work;
    if (xQueueReceive(workQueue, &work, pdMS_TO_TICKS(liveWanted() ? 1 : 10)) == pdTRUE) {
      doWork(work);
    } else if (lookAtPlate()) {
      Busy busy(Activity::Scanning);
      runScan();
    }
  }
}

}  // namespace

Activity workerActivity() { return activity; }

const char* activityText(Activity what) { return kActivityText[static_cast<int>(what)]; }

unsigned waitingJobs() { return workQueue ? uxQueueMessagesWaiting(workQueue) : 0; }

void startCamera() {
  cameraReady = cameraBegin();
  if (cameraReady && settings::jpegQuality != DEFAULT_JPEG_QUALITY) cameraSetQuality(settings::jpegQuality);
}

void workerBegin() {
  workQueue = xQueueCreate(WORK_QUEUE_LENGTH, sizeof(Work));
  xTaskCreatePinnedToCore(workerTask, "bin-worker", WORKER_TASK_STACK_BYTES, nullptr, 1, nullptr, xPortGetCoreID());
}

bool queueWork(const Work& work, const String& what) {
  const Activity now = activity;
  const bool busy = now != Activity::Free;
  const unsigned waiting = waitingJobs();
  if (xQueueSend(workQueue, &work, 0) != pdTRUE) {
    say("[busy] %u commands are already waiting, so \"%s\" was skipped. Try again in a moment.\n", waiting,
        what.c_str());
    return false;
  }
  if (busy && waiting) {
    say("[busy] %s now; \"%s\" runs after that and %u waiting command%s\n", activityText(now), what.c_str(), waiting,
        waiting == 1 ? "" : "s");
  } else if (busy) {
    say("[busy] %s now; \"%s\" runs after that\n", activityText(now), what.c_str());
  } else if (waiting) {
    say("[busy] \"%s\" runs after %u waiting command%s\n", what.c_str(), waiting, waiting == 1 ? "" : "s");
  }
  return true;
}

bool requestScan() {
  if (scanQueued || activity == Activity::Scanning) {
    say("[busy] a scan is already running or waiting, so this one was skipped\n");
    return false;
  }
  scanQueued = true;
  if (queueWork({Job::Scan, 0}, "scan")) return true;
  scanQueued = false;
  return false;
}
