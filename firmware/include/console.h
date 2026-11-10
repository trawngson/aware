// The board's serial console: a prompt and line editor in the style of zsh's
// robbyrussell theme, and output shared by the board's three tasks (the
// console in Arduino's loop, the worker and the link).
//
// The prompt sits on the last line with what you have typed. Anything a task
// prints goes above it: the console clears the prompt line, prints, and draws
// the prompt again. Every print must go through say() or hold a ConsoleLock
// for that to work, and so that nothing lands inside a photo for
// scripts/viewer.py. The chip's own messages go the same way: ESP-IDF's log
// ("I (123) wifi: ...") and the ROM print that cam_hal and Arduino core
// errors use. When another task holds the console, those lines wait and
// print as soon as it is free, so system tasks never wait. Only a crash
// report, or a print from an interrupt, still goes straight out.
//
// Keys: Enter, Backspace, Delete, Left/Right, Up/Down (history), Tab
// (completion), Home/End, Ctrl+A/E (start/end), Ctrl+B/F (left/right),
// Option+Left/Right (a word), Ctrl+W (delete a word), Ctrl+U (clear the
// line), Ctrl+K (delete to the end), Ctrl+L (clear the screen).
#pragma once

#include <Arduino.h>

#include <vector>

// Call once, right after Serial.begin().
void consoleBegin();

// Shows the prompt from now on. Call at the end of setup().
void consoleStartPrompt();

// Sets the prompt (with its colors) and redraws it if it changed.
void consoleSetPrompt(const String& prompt);

// Reads what has been typed, echoing and editing as it goes. Returns true
// with the line when Enter ends a line that isn't blank. Console task only.
bool consoleReadLine(String& line);

// Lists the words that could finish the last word of `before` (the line up
// to the cursor), for Tab.
using Completer = void (*)(const String& before, std::vector<const char*>& words);
void consoleSetCompleter(Completer completer);

// scripts/viewer.py sends this byte about once a second while it shows the
// live view. It is not echoed or kept in the line; the handler runs instead.
constexpr char kViewerHeartbeat = 0x1e;
void consoleSetHeartbeat(void (*handler)());

// Holds the console: other tasks wait to print until it ends. The outermost
// lock clears the prompt line first and draws the prompt again at the end.
// A quiet lock leaves the prompt line as it is: for photos, which the Mac
// takes out of the terminal before they show (see sendPhoto in scan.h), so
// the live view's frames don't make the prompt flash.
class ConsoleLock {
 public:
  explicit ConsoleLock(bool quiet = false);
  ~ConsoleLock();
  ConsoleLock(const ConsoleLock&) = delete;
  ConsoleLock& operator=(const ConsoleLock&) = delete;

 private:
  bool taken_ = false;
  bool quiet_ = false;
};

// Removes spaces, tabs and line breaks from both ends. Unlike String::trim it
// leaves the bytes of characters such as ’ or ệ alone.
void trimSpaces(String& text);

// Serial.printf above the prompt.
void say(const char* format, ...) __attribute__((format(printf, 1, 2)));
