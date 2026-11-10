// Joining the saved Wi-Fi network and reporting how it goes. Console only.
#pragma once

// Station mode, no power saving, reconnects by itself, the saved transmit
// power. Call once in setup().
void wifiBegin();

// Starts joining the saved network and returns; reportWifiChanges says how it
// went.
void startJoin();

// Call often: prints when Wi-Fi joins or drops, and gives up joining after
// WIFI_CONNECT_TIMEOUT_MS.
void reportWifiChanges();

bool wifiJoining();  // startJoin() is still waiting to join

// The saved transmit power ("txpower"); the radio rounds it to the steps it has.
void applyTxPower();
float txPowerNow();  // what the radio uses, in dBm
