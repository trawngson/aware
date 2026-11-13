// AWARE bin MVP: one ESP32-S3 camera board and one servo.
//
// Press the BOOT button (or type "scan"): the board photographs the plate,
// sends the JPEG to the detection server (or, in LLM mode, to an OpenAI model;
// llm.h), routes the detections with the routing-v1 rules, and turns the servo
// to that stream's angle. It holds there, then returns home. On any failure it
// holds: the servo stays home (scan.cpp).
//
// Five tasks share the work, so typed commands are read at all times, even
// during a scan:
// - the console (Arduino's loop, below) runs the prompt (console.cpp), the
//   BOOT button and Wi-Fi changes (wifi_join.cpp), and at once every command
//   that only reads or saves settings (commands.cpp, settings.cpp);
// - the worker (worker.cpp) owns the camera, the servo (servo.cpp) and the
//   LED. It watches the plate (plate_watch.cpp), scans, and runs "scan",
//   "snap", "servo" and "angle" in the order they came;
// - the link task keeps the server connection open (server_link.cpp);
// - the sign-in task signs in to ChatGPT and renews it, for LLM mode (llm.cpp);
// - the IMU task reads the MPU-6050 under the plate, if there is one (imu.cpp).

#include <Arduino.h>

#include "commands.h"
#include "config.h"
#include "console.h"
#include "imu.h"
#include "llm.h"
#include "plate_watch.h"
#include "server_link.h"
#include "servo.h"
#include "settings.h"
#include "status_led.h"
#include "status_report.h"
#include "wifi_join.h"
#include "worker.h"

namespace {

void pollButton() {
  static bool pressed = false;
  static uint32_t changedAt = 0;
  const bool now = digitalRead(BUTTON_PIN) == LOW;
  if (now != pressed && millis() - changedAt > BUTTON_DEBOUNCE_MS) {
    pressed = now;
    changedAt = millis();
    if (pressed) requestScan();
  }
}

}  // namespace

void setup() {
  Serial.begin(SERIAL_BAUD);  // fast enough for the live view and a photo within the dwell
  delay(500);
  consoleBegin();
  consoleSetCompleter(completeWords);
  consoleSetHeartbeat(liveKeepOn);
  // The console (this task) runs ahead of the worker and link tasks, so it
  // answers at once. It only ever waits briefly.
  vTaskPrioritySet(nullptr, 2);
#ifdef AWARE_SIMULATOR
  say("\nAWARE bin MVP %s (Wokwi simulator)\n", FIRMWARE_VERSION);
#else
  say("\nAWARE bin MVP %s\n", FIRMWARE_VERSION);
#endif

  pinMode(BUTTON_PIN, INPUT_PULLUP);
  settings::load();
  ledBegin();
  servoBegin();
  imuBegin();
  startCamera();

  wifiBegin();
  linkBegin();
  llmBegin();
  pointLink();
  if (!settings::wifiSsid.isEmpty()) startJoin();  // the link connects once Wi-Fi has joined

  workerBegin();

  printStatus();
  say("Ready. Press BOOT or type \"scan\". Type \"help\" for all commands.\n");
  consoleSetPrompt(buildPrompt());
  consoleStartPrompt();
}

void loop() {
  String line;
  if (consoleReadLine(line)) {
    ConsoleLock lock;  // the prompt comes back, updated, when the command ends
    handleCommand(line);
    consoleSetPrompt(buildPrompt());
  }
  pollButton();
  reportWifiChanges();
  delay(5);
}
