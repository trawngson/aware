#include "wifi_join.h"

#include <Arduino.h>
#include <WiFi.h>

#include "config.h"
#include "console.h"
#include "esp_wifi.h"
#include "server_link.h"
#include "settings.h"

namespace {

bool joining = false;  // startJoin() started joining Wi-Fi
uint32_t joinStartedAt = 0;

}  // namespace

void wifiBegin() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.setAutoReconnect(true);
  applyTxPower();
}

void startJoin() {
  const String& ssid = settings::wifiSsid;
  const String& pass = settings::wifiPass;
  if (ssid.isEmpty()) {
    say("[wifi] no network set. Type \"ssid <name>\", then \"pass <password>\", then \"connect\"\n");
    return;
  }
  say("[wifi] joining \"%s\"\n", ssid.c_str());
  WiFi.disconnect();
#ifdef AWARE_SIMULATOR
  // Wokwi's access point is on channel 6; naming it skips a 4 s scan.
  if (ssid == "Wokwi-GUEST") {
    WiFi.begin(ssid.c_str(), pass.c_str(), 6);
  } else {
    WiFi.begin(ssid.c_str(), pass.c_str());
  }
#else
  WiFi.begin(ssid.c_str(), pass.c_str());
#endif
  joining = true;
  joinStartedAt = millis();
}

void reportWifiChanges() {
  static bool wasConnected = false;
  const bool connected = WiFi.status() == WL_CONNECTED;
  if (connected != wasConnected) {
    wasConnected = connected;
    if (connected) {
      say("[wifi] connected, IP %s\n", WiFi.localIP().toString().c_str());
      configTime(0, 0, "pool.ntp.org", "time.google.com");  // UTC; LLM mode checks when its token runs out
      linkConnectSoon();
    } else {
      say("[wifi] disconnected\n");
    }
  }
  if (connected) {
    joining = false;
  } else if (joining && millis() - joinStartedAt > WIFI_CONNECT_TIMEOUT_MS) {
    joining = false;
    say("[wifi] could not join. Check the name and password; the board only sees 2.4 GHz networks.\n");
  }
}

bool wifiJoining() { return joining; }

// The radio takes the power in quarter dBm.
void applyTxPower() { esp_wifi_set_max_tx_power(static_cast<int8_t>(settings::wifiTxDbm * 4)); }

float txPowerNow() {
  int8_t quarters = 0;
  return esp_wifi_get_max_tx_power(&quarters) == ESP_OK ? quarters / 4.0f : 0;
}
