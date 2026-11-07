// OV2640 camera on the ESP32-S3 N16R8 CAM board. The simulator build uses
// camera_sim.cpp instead.
#ifndef AWARE_SIMULATOR

#include <Arduino.h>

#include "camera.h"
#include "console.h"
#include "config.h"
#include "esp_camera.h"
#include "img_converters.h"

bool cameraBegin() {
  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0;
  c.ledc_timer = LEDC_TIMER_0;
  c.pin_d0 = CAM_PIN_Y2;
  c.pin_d1 = CAM_PIN_Y3;
  c.pin_d2 = CAM_PIN_Y4;
  c.pin_d3 = CAM_PIN_Y5;
  c.pin_d4 = CAM_PIN_Y6;
  c.pin_d5 = CAM_PIN_Y7;
  c.pin_d6 = CAM_PIN_Y8;
  c.pin_d7 = CAM_PIN_Y9;
  c.pin_xclk = CAM_PIN_XCLK;
  c.pin_pclk = CAM_PIN_PCLK;
  c.pin_vsync = CAM_PIN_VSYNC;
  c.pin_href = CAM_PIN_HREF;
  c.pin_sccb_sda = CAM_PIN_SIOD;
  c.pin_sccb_scl = CAM_PIN_SIOC;
  c.pin_pwdn = CAM_PIN_PWDN;
  c.pin_reset = CAM_PIN_RESET;
  c.xclk_freq_hz = 20000000;
  c.pixel_format = PIXFORMAT_JPEG;
  c.frame_size = FRAME_SIZE;
  c.jpeg_quality = DEFAULT_JPEG_QUALITY;
  c.grab_mode = CAMERA_GRAB_LATEST;
  if (psramFound()) {
    c.fb_location = CAMERA_FB_IN_PSRAM;
    c.fb_count = 2;
    c.jpeg_buffer_size = JPEG_BUFFER_BYTES;
  } else {
    say("[camera] no PSRAM found: is this an N16R8 board? Falling back to 320x240.\n");
    c.fb_location = CAMERA_FB_IN_DRAM;
    c.fb_count = 1;
    c.frame_size = FRAMESIZE_QVGA;
  }
  const esp_err_t err = esp_camera_init(&c);
  if (err != ESP_OK) {
    say("[camera] start failed (0x%x). Check the ribbon cable and the camera pins in config.h.\n", err);
    return false;
  }
  say("[camera] ready\n");
  return true;
}

void cameraEnd() { esp_camera_deinit(); }

// CAMERA_GRAB_LATEST hands back the newest finished frame, at most one frame
// old, so no frame is thrown away first.
bool cameraTake(Photo& photo) {
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) return false;
  photo.data = fb->buf;
  photo.length = fb->len;
  photo.width = fb->width;
  photo.height = fb->height;
  photo.name = nullptr;
  photo.handle = fb;
  return true;
}

void cameraRelease(Photo& photo) {
  if (photo.handle) esp_camera_fb_return(static_cast<camera_fb_t*>(photo.handle));
  photo = Photo();
}

// Decodes the 640 x 480 JPEG at 1/8 size, then turns each pixel grey.
bool cameraThumbnail(const Photo& photo, uint8_t* grey) {
  static uint16_t rgb[THUMB_PIXELS];
  const bool ok = photo.width == 640 && photo.height == 480 &&
                  jpg2rgb565(photo.data, photo.length, reinterpret_cast<uint8_t*>(rgb), JPG_SCALE_8X);
  if (!ok) return false;
  for (int i = 0; i < THUMB_PIXELS; ++i) {
    const int r = (rgb[i] >> 11) << 3, g = ((rgb[i] >> 5) & 0x3F) << 2, b = (rgb[i] & 0x1F) << 3;
    grey[i] = (r * 77 + g * 150 + b * 29) >> 8;
  }
  return true;
}

void cameraSetQuality(int quality) {
  sensor_t* sensor = esp_camera_sensor_get();
  if (sensor) sensor->set_quality(sensor, quality);
}

const char* cameraModel() {
  sensor_t* sensor = esp_camera_sensor_get();
  const camera_sensor_info_t* info = sensor ? esp_camera_sensor_get_info(&sensor->id) : nullptr;
  return info ? info->name : "unknown camera";
}

bool cameraListPhotos() {
  say("Photo files exist only in the simulator build.\n");
  return false;
}

bool cameraChoosePhoto(int) { return cameraListPhotos(); }

#endif  // AWARE_SIMULATOR
