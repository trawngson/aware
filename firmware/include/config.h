// Pins, timings and defaults for the bin MVP. Settings typed over serial
// (Wi-Fi, server, angles) are saved on the board and override the defaults.
#pragma once

#include <Arduino.h>

#include "esp_camera.h"

#define FIRMWARE_VERSION "mvp-0.7.0"

// Camera: ESP32-S3 N16R8 CAM boards with an OV2640 use the ESP32-S3-EYE
// (Freenove) camera pins.
constexpr int CAM_PIN_PWDN = -1;
constexpr int CAM_PIN_RESET = -1;
constexpr int CAM_PIN_XCLK = 15;
constexpr int CAM_PIN_SIOD = 4;
constexpr int CAM_PIN_SIOC = 5;
constexpr int CAM_PIN_Y9 = 16;
constexpr int CAM_PIN_Y8 = 17;
constexpr int CAM_PIN_Y7 = 18;
constexpr int CAM_PIN_Y6 = 12;
constexpr int CAM_PIN_Y5 = 10;
constexpr int CAM_PIN_Y4 = 8;
constexpr int CAM_PIN_Y3 = 9;
constexpr int CAM_PIN_Y2 = 11;
constexpr int CAM_PIN_VSYNC = 6;
constexpr int CAM_PIN_HREF = 7;
constexpr int CAM_PIN_PCLK = 13;

// 640 x 480 matches the model's 640 px input.
constexpr framesize_t FRAME_SIZE = FRAMESIZE_VGA;
// 0-63, lower is better and bigger. Every byte crosses a slow upload link
// (see server_link.h); "quality" changes it.
constexpr int DEFAULT_JPEG_QUALITY = 12;
// Room for one JPEG frame, in PSRAM, twice (two frame buffers). The camera
// driver's default, 640 x 480 / 5 = 60 KB, is too small for a detailed or
// dim (grainy) scene: frames that don't fit are dropped with "cam_hal: FB-OVF".
constexpr size_t JPEG_BUFFER_BYTES = 160 * 1024;

// Servo signal pin. GPIO 14 is free on these boards (not camera, PSRAM or USB).
constexpr int SERVO_PIN = 14;
// The camera clock uses LEDC channel 0 on timer 0; channel 4 runs on timer 2.
constexpr int SERVO_LEDC_CHANNEL = 4;
constexpr int SERVO_LEDC_BITS = 14;
constexpr int SERVO_FREQ_HZ = 50;
constexpr uint32_t SERVO_PERIOD_US = 20000;
constexpr uint32_t SERVO_MIN_PULSE_US = 500;   // 0 degrees
constexpr uint32_t SERVO_MAX_PULSE_US = 2500;  // 180 degrees
// Ramp speed in degrees a second; 0 jumps straight to the angle. An MG996R
// tops out near 350-430 degrees a second. "speed" changes it.
constexpr int DEFAULT_SERVO_SPEED_DPS = 300;
constexpr uint32_t DWELL_MS = 1000;            // time held at a destination

// Default angles. routing-v1: liner 1 paper, liner 2 plastic bottles,
// liners 3 and 4 other. One servo can only point at one place per stream.
constexpr int DEFAULT_ANGLE_HOME = 90;
constexpr int DEFAULT_ANGLE_PAPER = 45;
constexpr int DEFAULT_ANGLE_BOTTLES = 135;
constexpr int DEFAULT_ANGLE_OTHER = 180;

// RGB status LED (WS2812, status_led.h): blue while scanning, green when
// sorted, red when held. GPIO 48 is the built-in RGB LED on ESP32-S3
// DevKitC-1 style boards, N16R8 CAM boards included.
constexpr uint8_t LED_PIN = 48;
constexpr uint8_t LED_BRIGHTNESS = 40;     // of 255; full brightness is blinding
constexpr uint32_t LED_RESULT_MS = 3000;   // how long green or red stays on

// The BOOT button starts a scan once the board is running.
constexpr int BUTTON_PIN = 0;
constexpr uint32_t BUTTON_DEBOUNCE_MS = 50;

// A detection below this confidence sends the plate to other (routing-v1).
// Placeholder until it is set on a bin-domain test set; "conf" changes it.
constexpr float DEFAULT_MIN_CONFIDENCE = 0.5f;

constexpr uint32_t WIFI_CONNECT_TIMEOUT_MS = 15000;
// Wi-Fi transmit power in dBm (2-21); "txpower" changes it, saved. 19.5 is
// the chip's maximum. Some boards' power supply or antenna can't keep up at
// full power, and their packets get through more often a little lower.
constexpr float DEFAULT_WIFI_TX_DBM = 19.5f;
constexpr int32_t HTTP_CONNECT_TIMEOUT_MS = 10000;
constexpr int TLS_HANDSHAKE_TIMEOUT_S = 30;
// The server may need a cold start after it has been idle.
constexpr uint32_t HTTP_TIMEOUT_MS = 60000;
// The kept-open server connection (server_link.cpp): how often to check it,
// and how long to wait before reconnecting after a failure.
constexpr uint32_t LINK_CHECK_INTERVAL_MS = 1000;
constexpr uint32_t LINK_RETRY_MIN_MS = 2000;
constexpr uint32_t LINK_RETRY_MAX_MS = 60000;
constexpr size_t MAX_REPLY_BYTES = 16384;

// Tasks (see main.cpp). Both stacks have room for a TLS handshake.
constexpr uint32_t WORKER_TASK_STACK_BYTES = 16384;
constexpr uint32_t LINK_TASK_STACK_BYTES = 12288;
// Commands for the camera and servo ("scan", "snap", "servo", "angle") that
// can wait while one runs.
constexpr int WORK_QUEUE_LENGTH = 8;

// Serial speed for the log, commands, photos and the live view. The USB chip
// (CH343) and the ESP32-S3 both handle 2 Mbit/s; a 640 x 480 frame of about
// 11 KB then takes about 75 ms, so the live view runs near 10 frames a second.
// The chip's own boot messages stay at 115200, so a few garbled characters at
// reset are normal. platformio.ini (monitor_speed) and scripts/viewer.py use
// the same speed.
constexpr uint32_t SERIAL_BAUD = 2000000;
// The viewer sends a heartbeat every second while it shows the live view;
// the board stops streaming this long after the last one.
constexpr uint32_t LIVE_HOLD_MS = 3000;

// Optional untracked include/local_settings.h (see local_settings.example.h)
// supplies defaults that stay out of git, such as the server address.
#if __has_include("local_settings.h")
#include "local_settings.h"
#endif
#ifndef LOCAL_SERVER_URL
#define LOCAL_SERVER_URL ""
#endif
#ifndef LOCAL_WIFI_SSID
#define LOCAL_WIFI_SSID ""
#endif
#ifndef LOCAL_WIFI_PASS
#define LOCAL_WIFI_PASS ""
#endif

// Untracked include/secrets.h (see secrets.example.h) holds the token the
// detection server asks for. Without it every scan would be refused.
#if __has_include("secrets.h")
#include "secrets.h"
#endif
#ifndef BIN_TOKEN
#error "No bin token: copy include/secrets.example.h to include/secrets.h and paste the token"
#endif

// In the Wokwi simulator the only network is its open access point.
#ifdef AWARE_SIMULATOR
#undef LOCAL_WIFI_SSID
#undef LOCAL_WIFI_PASS
#define LOCAL_WIFI_SSID "Wokwi-GUEST"
#define LOCAL_WIFI_PASS ""
#endif

// LLM mode ("mode llm"; README, LLM mode): the board sends the photo straight
// to an OpenAI model through the ChatGPT sign-in that Codex uses ("llm login"),
// instead of to the detection server. The question it asks is in llm_prompt.h.
#define LLM_URL "https://chatgpt.com/backend-api/codex/responses"
// "llm model" changes it, saved.
#define LLM_DEFAULT_MODEL "gpt-6-luna"
// With the 18-label prompt (2026-11-07, scripts/llm_latency.py, sim/photos
// twice) "low" and "none" both sorted all 22 right; "low" took a median of
// 1.6 s (slowest 3.3 s), "none" 1.8 s (slowest 2.5 s).
#define LLM_REASONING_EFFORT "low"
// "low" shrinks the photo to 512 px before the model sees it, and then small
// items get mixed up (a paper cup among bottles); "high" was no slower.
#define LLM_IMAGE_DETAIL "high"
// The answer usually comes in 1-2 s; a stuck request holds after this.
constexpr uint32_t LLM_TIMEOUT_MS = 15000;
// The reply streams 15-25 KB of events; the answer is one of them.
constexpr size_t LLM_MAX_REPLY_BYTES = 65536;
// Sign-in: the device-code flow and client ID of OpenAI's Codex CLI.
#define OPENAI_AUTH_HOST "auth.openai.com"
#define CODEX_CLIENT_ID "app_EMoamEEZ73f0CkXaXp7hrann"
// Access tokens last 10 days; the board renews its own this long before
// they run out, in the background.
constexpr uint32_t LLM_REFRESH_AHEAD_S = 24 * 3600;
constexpr uint32_t LLM_LOGIN_TIMEOUT_MS = 15 * 60 * 1000;  // to type the code
constexpr uint32_t LLM_AUTH_CHECK_MS = 60000;              // how often to check the token
constexpr uint32_t LLM_AUTH_TASK_STACK_BYTES = 16384;      // TLS and two tokens' JSON

// Detections beyond this many send the plate to other.
constexpr size_t MAX_DETECTIONS = 32;

// Automatic scans: the camera checks the plate this often, and scans once
// enough of it differs from the empty plate and has stopped moving. All are
// first guesses until tested on the bin.
constexpr uint32_t WATCH_INTERVAL_MS = 100;
constexpr int WATCH_PIXEL_DIFF = 24;          // grey levels (of 255) that count as changed
constexpr float WATCH_ITEM_SHARE = 0.01f;     // changed from the empty plate: an item
constexpr float WATCH_STILL_SHARE = 0.005f;   // changed since the last check below this: still
constexpr int WATCH_STILL_CHECKS = 2;         // still checks in a row before a scan
// With the IMU in use (imu.h), a felt impact lowers the share that counts as
// an item, and a change this big with no impact is the light (presence.h).
// Kept high: a sheet of paper that floats down flat may not jolt the plate,
// yet covers half the view. Above 1 turns the rule off.
constexpr float WATCH_FELT_SHARE = 0.002f;
constexpr float WATCH_LIGHT_SHARE = 0.8f;

// IMU: an MPU-6050 under the plate, optional (imu.h). It uses I2C port 0;
// the camera's SCCB has port 1. GPIO 1 and 2 are free on these boards (not
// camera, PSRAM, SD card, USB or strapping pins).
constexpr int IMU_PIN_SDA = 1;
constexpr int IMU_PIN_SCL = 2;
constexpr uint32_t IMU_I2C_HZ = 100000;  // slow and sure over the wires out to the plate
constexpr uint32_t IMU_SAMPLE_HZ = 200;
constexpr uint32_t IMU_RETRY_MS = 1000;  // how often it looks for a missing chip
constexpr uint32_t IMU_TASK_STACK_BYTES = 4096;
// Checks around each tip. All are first guesses until tested on the bin.
constexpr float IMU_LEVEL_TOLERANCE_DEG = 3.0f;  // off level at home: the scan holds
constexpr float IMU_MIN_TIP_DEG = 10.0f;         // less at a bin: the plate didn't tip
constexpr uint32_t IMU_SETTLE_MS = 500;          // longest wait for the plate to stop moving
constexpr uint32_t IMU_STILL_MS = 100;           // still this long counts as settled
// Impacts: shake is how far the acceleration is from its slow average
// (imu_math.h). The "imu" command shows the last impact's peak, for tuning.
constexpr float IMU_STILL_G = 0.03f;
constexpr float IMU_IMPACT_G = 0.08f;
constexpr float IMU_REARM_G = 0.04f;
constexpr uint32_t IMU_IMPACT_GAP_MS = 300;    // bounces closer than this are one impact
constexpr uint32_t IMU_AFTER_MOVE_MS = 500;    // the servo's own jolts: no impacts until then
constexpr uint32_t IMU_FELT_WINDOW_MS = 10000; // an impact older than this is forgotten
constexpr uint32_t IMU_BUMP_AFTER_MS = 1000;   // time for the camera to see what landed
