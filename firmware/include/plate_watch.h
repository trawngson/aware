// Automatic scans and the live view (worker).
//
// Every WATCH_INTERVAL_MS the camera compares the plate with the last check
// and with the empty plate. Once enough differs from the empty plate and
// nothing has moved for WATCH_STILL_CHECKS checks, the board scans. Things
// that move and leave nothing behind, such as a hand or a shadow, don't.
// While the viewer asks for the live view, every frame also goes to it, as
// fast as the cable carries them, and the plate is checked on each frame.
#pragma once

#ifdef AWARE_SIMULATOR
constexpr bool kLiveCamera = false;  // its "camera" hands out sim/photos in turn, one per scan
#else
constexpr bool kLiveCamera = true;
#endif

// One look at the plate: a frame for the live view, the automatic-scan check,
// or both. True when an item has landed and stopped moving: then the worker
// scans. Worker only.
bool lookAtPlate();

// The viewer's heartbeat keeps the live view on for LIVE_HOLD_MS more.
void liveKeepOn();
// "feed off": stops streaming now, not after LIVE_HOLD_MS.
void liveStop();
bool liveWanted();
