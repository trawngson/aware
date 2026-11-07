// Pins, timings and defaults for the bin MVP. Settings typed over serial
// (Wi-Fi, server, angles) are saved on the board and override the defaults.
#pragma once

#include <Arduino.h>

#include "esp_camera.h"

#define FIRMWARE_VERSION "mvp-0.2.1"

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

// The BOOT button starts a scan once the board is running.
constexpr int BUTTON_PIN = 0;
constexpr uint32_t BUTTON_DEBOUNCE_MS = 50;

// A detection below this confidence sends the plate to other (routing-v1).
// Placeholder until it is set on a bin-domain test set; "conf" changes it.
constexpr float DEFAULT_MIN_CONFIDENCE = 0.5f;

constexpr uint32_t WIFI_CONNECT_TIMEOUT_MS = 15000;
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
