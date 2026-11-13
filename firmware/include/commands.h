// The serial commands ("help" lists them). Commands that only read or save
// settings run at once; the ones that need the camera or servo go to the
// worker (worker.h). Console only.
#pragma once

#include <Arduino.h>

#include <vector>

// Runs one typed line.
void handleCommand(String line);

// For Tab: the commands, then the names after "angle", "auto" and the like.
void completeWords(const String& before, std::vector<const char*>& words);

// Like zsh's robbyrussell theme ("➜  ~"): the arrow turns red after a failed
// command.
String buildPrompt();

// Opens the link to the server the mode uses, ahead of the next scan: in
// setup(), and after "server" or "mode".
void pointLink();
