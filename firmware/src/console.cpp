#include "console.h"

#include <algorithm>
#include <cstdarg>
#include <cstring>

#include "esp_log.h"
#include "esp_rom_sys.h"
#include "esp_rom_uart.h"

namespace {

constexpr const char* kClearLine = "\r\x1b[2K";  // to the line's start, then clear it
constexpr size_t kMaxLine = 200;
constexpr int kHistory = 20;

// ---- State used only while holding `mutex` -----------------------------------

SemaphoreHandle_t mutex = nullptr;  // recursive: a lock holder may call say()
int depth = 0;                      // ConsoleLock nesting
bool promptOn = false;              // consoleStartPrompt() has run
bool promptShown = false;           // the prompt and typed line are on screen
bool romOutput = false;             // printing a ROM line: write through the ROM, not Serial
String prompt = "> ";
String line;  // typed so far
size_t cursor = 0;

String history[kHistory];
int historyCount = 0;
int historyNewest = -1;
int browsing = 0;  // 0: a new line; n: the n-th newest entry is shown
String draft;      // the new line, kept while browsing

enum class Escape : uint8_t { None, Start, Csi, Ss3 };
Escape escape = Escape::None;
String escapeParams;
bool lastWasCr = false;  // Enter sends "\r\n" from the PlatformIO monitor

Completer completer = nullptr;
void (*heartbeat)() = nullptr;

// ---- The chip's own log, kept while another task holds the console ------------
// A system task (Wi-Fi, the camera driver) must never wait for the console,
// so a line it prints while the console is busy waits here instead, and the
// next task to let go of the console prints it. Appending is guarded by a
// spinlock, so any task on either core can add a line.

constexpr size_t kPendingBytes = 4096;
char pending[kPendingBytes];
size_t pendingLength = 0;
uint32_t droppedLines = 0;
portMUX_TYPE pendingMux = portMUX_INITIALIZER_UNLOCKED;

void queueLine(const char* text, size_t length) {
  portENTER_CRITICAL(&pendingMux);
  if (pendingLength + length <= kPendingBytes) {
    memcpy(pending + pendingLength, text, length);
    pendingLength += length;
  } else {
    ++droppedLines;
  }
  portEXIT_CRITICAL(&pendingMux);
}

// ---- Output --------------------------------------------------------------------

void emit(const char* text, size_t length) {
  if (romOutput) {
    for (size_t i = 0; i < length; ++i) esp_rom_output_tx_one_char(static_cast<uint8_t>(text[i]));
  } else {
    Serial.write(reinterpret_cast<const uint8_t*>(text), length);
  }
}

void emit(const char* text) { emit(text, strlen(text)); }
void emit(const String& text) { emit(text.c_str(), text.length()); }

// With the console held: prints the lines that waited. Lines added meanwhile
// go after the part being printed, so only that part is removed afterwards.
void flushPending() {
  portENTER_CRITICAL(&pendingMux);
  const size_t length = pendingLength;
  const uint32_t dropped = droppedLines;
  droppedLines = 0;
  portEXIT_CRITICAL(&pendingMux);
  if (length > 0) {
    emit(pending, length);
    portENTER_CRITICAL(&pendingMux);
    memmove(pending, pending + length, pendingLength - length);
    pendingLength -= length;
    portEXIT_CRITICAL(&pendingMux);
  }
  if (dropped > 0) {
    char note[80];
    snprintf(note, sizeof(note), "[console] %u log lines were dropped: too many at once\r\n",
             static_cast<unsigned>(dropped));
    emit(note);
  }
}

// ---- UTF-8 ----------------------------------------------------------------------
// The line holds UTF-8, as the Mac's terminal sends it: a character is 1-4
// bytes, and the first byte says how many. The cursor always sits between
// whole characters.

bool isContinuation(uint8_t byte) { return (byte & 0xC0) == 0x80; }

size_t utf8Length(uint8_t lead) {
  if (lead < 0x80) return 1;
  if ((lead & 0xE0) == 0xC0) return 2;
  if ((lead & 0xF0) == 0xE0) return 3;
  if ((lead & 0xF8) == 0xF0) return 4;
  return 0;  // a continuation byte, or not UTF-8
}

size_t previousChar(size_t i) {
  if (i == 0) return 0;
  do {
    --i;
  } while (i > 0 && isContinuation(static_cast<uint8_t>(line[i])));
  return i;
}

size_t nextChar(size_t i) {
  if (i >= line.length()) return line.length();
  do {
    ++i;
  } while (i < line.length() && isContinuation(static_cast<uint8_t>(line[i])));
  return i;
}

uint32_t codePointAt(size_t i, size_t& length) {
  const uint8_t lead = static_cast<uint8_t>(line[i]);
  length = utf8Length(lead);
  if (length < 2 || i + length > line.length()) {
    length = 1;
    return lead;
  }
  uint32_t code = lead & (0x7F >> length);
  for (size_t k = 1; k < length; ++k) code = (code << 6) | (static_cast<uint8_t>(line[i + k]) & 0x3F);
  return code;
}

// Terminal columns: 2 for East Asian wide characters and emoji, 0 for
// combining accents, 1 for the rest (Latin, Vietnamese, ’ and so on).
size_t columnsOf(uint32_t code) {
  if (code >= 0x0300 && code <= 0x036F) return 0;
  if ((code >= 0x1100 && code <= 0x115F) || (code >= 0x2E80 && code <= 0xA4CF) || (code >= 0xAC00 && code <= 0xD7A3) ||
      (code >= 0xF900 && code <= 0xFAFF) || (code >= 0xFE30 && code <= 0xFE4F) || (code >= 0xFF00 && code <= 0xFF60) ||
      (code >= 0xFFE0 && code <= 0xFFE6) || (code >= 0x1F300 && code <= 0x1FAFF) || (code >= 0x20000 && code <= 0x3FFFD)) {
    return 2;
  }
  return 1;
}

size_t columnsBetween(size_t from, size_t to) {
  size_t columns = 0;
  while (from < to) {
    size_t length = 1;
    columns += columnsOf(codePointAt(from, length));
    from += length;
  }
  return columns;
}

// A character arriving byte by byte from the terminal.
char typed[4];
size_t typedHave = 0;
size_t typedNeed = 0;

void drawPrompt() {
  emit(prompt);
  emit(line);
  const size_t back = columnsBetween(cursor, line.length());
  if (back > 0) {
    char move[16];  // ESC [ up to 10 digits D
    snprintf(move, sizeof(move), "\x1b[%uD", static_cast<unsigned>(back));
    emit(move);
  }
  promptShown = true;
}

void redraw() {
  emit(kClearLine);
  drawPrompt();
}

// The outermost holder clears the prompt line and prints the lines that
// waited before printing...
void enter() {
  if (depth++ > 0) return;
  if (promptShown) {
    emit(kClearLine);
    promptShown = false;
  }
  flushPending();
}

// ...and at the end prints any that came meanwhile and draws the prompt again.
void leave() {
  if (--depth > 0) return;
  flushPending();
  if (promptOn && !promptShown) drawPrompt();
}

// ---- The chip's own messages ------------------------------------------------------
// Two ways in: ESP-IDF's log ("I (123) wifi: ..."), which the Wi-Fi driver
// prints in pieces (the "I (123) wifi:" part, then the message), and the ROM
// print (ets_printf) that cam_hal and Arduino core errors use, one character
// at a time. Each gathers into whole lines that go above the prompt like any
// other, written through the ROM so they never wait for Serial (an Arduino
// core error may come from inside Serial). In an interrupt, a critical
// section, a crash report or before the scheduler starts, a ROM character
// goes straight out as it always did: nothing there may wait or touch flash.

struct PartLine {
  char text[256];
  size_t length = 0;
  TickType_t startedAt = 0;
  portMUX_TYPE mux = portMUX_INITIALIZER_UNLOCKED;
};
PartLine romPart;  // ROM print
PartLine logPart;  // ESP-IDF log

// Adds text; returns true once the line has ended (or the buffer is full).
bool IRAM_ATTR addToLine(PartLine& part, const char* text, size_t length) {
  portENTER_CRITICAL_SAFE(&part.mux);
  if (part.length == 0) part.startedAt = xTaskGetTickCount();
  bool ended = false;
  for (size_t i = 0; i < length && part.length < sizeof(part.text); ++i) {
    part.text[part.length++] = text[i];
    ended = text[i] == '\n';
  }
  ended = ended || part.length == sizeof(part.text);
  portEXIT_CRITICAL_SAFE(&part.mux);
  return ended;
}

// In a task, with flash readable: prints the gathered line, or keeps it for
// later when another task holds the console.
void __attribute__((noinline)) printLine(PartLine& part) {
  char text[sizeof(part.text)];
  portENTER_CRITICAL(&part.mux);
  const size_t length = part.length;
  memcpy(text, part.text, length);
  part.length = 0;
  portEXIT_CRITICAL(&part.mux);
  if (length == 0) return;
  if (mutex && xSemaphoreTakeRecursive(mutex, 0) == pdTRUE) {
    const bool wasRom = romOutput;
    romOutput = true;
    enter();
    for (size_t i = 0; i < length; ++i) esp_rom_output_putc(text[i]);  // "\n" becomes "\r\n", as before
    leave();
    romOutput = wasRom;
    xSemaphoreGiveRecursive(mutex);
  } else {
    queueLine(text, length);
  }
}

void IRAM_ATTR romPutc(char c) {
  if (xPortInIsrContext() || !xPortCanYield() || xTaskGetSchedulerState() != taskSCHEDULER_RUNNING) {
    esp_rom_output_putc(c);
    return;
  }
  if (addToLine(romPart, &c, 1)) printLine(romPart);
}

int systemLog(const char* format, va_list args) {
  char text[192];
  const int n = vsnprintf(text, sizeof(text), format, args);
  if (n <= 0) return n;
  const size_t length = std::min(static_cast<size_t>(n), sizeof(text) - 1);
  if (!mutex || xTaskGetSchedulerState() != taskSCHEDULER_RUNNING) {
    for (size_t i = 0; i < length; ++i) esp_rom_output_putc(text[i]);
    return n;
  }
  if (addToLine(logPart, text, length)) printLine(logPart);
  return n;
}

// A line that hasn't ended after a while (a print without a newline) goes
// out as it is.
void printStaleLines() {
  for (PartLine* part : {&romPart, &logPart}) {
    portENTER_CRITICAL(&part->mux);
    const bool stale = part->length > 0 && xTaskGetTickCount() - part->startedAt > pdMS_TO_TICKS(200);
    portEXIT_CRITICAL(&part->mux);
    if (stale) printLine(*part);
  }
}

// ---- History -----------------------------------------------------------------

const String& historyEntry(int n) {  // 1 is the newest
  return history[(historyNewest - (n - 1) + kHistory) % kHistory];
}

void remember(const String& entry) {
  if (historyCount > 0 && historyEntry(1) == entry) return;  // like zsh's HIST_IGNORE_DUPS
  historyNewest = (historyNewest + 1) % kHistory;
  history[historyNewest] = entry;
  if (historyCount < kHistory) ++historyCount;
}

void showEntry(int n) {
  browsing = n;
  line = n == 0 ? draft : historyEntry(n);
  cursor = line.length();
  redraw();
}

void historyUp() {
  if (browsing >= historyCount) return;
  if (browsing == 0) draft = line;
  showEntry(browsing + 1);
}

void historyDown() {
  if (browsing > 0) showEntry(browsing - 1);
}

// ---- Editing -----------------------------------------------------------------

void moveTo(size_t position) {
  cursor = position;
  redraw();
}

size_t wordLeft() {
  size_t i = cursor;
  while (i > 0 && line[i - 1] == ' ') --i;
  while (i > 0 && line[i - 1] != ' ') --i;
  return i;
}

size_t wordRight() {
  size_t i = cursor;
  while (i < line.length() && line[i] == ' ') ++i;
  while (i < line.length() && line[i] != ' ') ++i;
  return i;
}

// Inserts one whole character (1-4 bytes) at the cursor.
void insert(const char* bytes, size_t length) {
  if (line.length() + length > kMaxLine) return;
  const bool atEnd = cursor == line.length();
  String character;
  character.concat(bytes, length);
  line = line.substring(0, cursor) + character + line.substring(cursor);
  cursor += length;
  if (atEnd && promptShown) {
    emit(bytes, length);
  } else {
    redraw();
  }
}

void backspace() {
  if (cursor == 0) return;
  const bool atEnd = cursor == line.length();
  const size_t start = previousChar(cursor);
  const bool oneColumn = cursor - start == 1;  // plain ASCII
  line.remove(start, cursor - start);
  cursor = start;
  if (atEnd && promptShown && oneColumn) {
    emit("\b \b");
  } else {
    redraw();
  }
}

void deleteForward() {
  if (cursor >= line.length()) return;
  line.remove(cursor, nextChar(cursor) - cursor);
  redraw();
}

void deleteWordBack() {
  const size_t start = wordLeft();
  line.remove(start, cursor - start);
  cursor = start;
  redraw();
}

void setLine(const String& text) {
  line = text;
  cursor = line.length();
  redraw();
}

// Tab: finishes the word before the cursor when only one word fits, or as
// far as all the fitting words agree; otherwise lists them, like zsh.
void complete() {
  if (!completer) return;
  const String before = line.substring(0, cursor);
  const int wordStart = before.lastIndexOf(' ') + 1;
  const String word = before.substring(wordStart);
  std::vector<const char*> words;
  completer(before, words);
  std::vector<String> fits;
  for (const char* w : words) {
    if (String(w).startsWith(word)) fits.emplace_back(w);
  }
  if (fits.empty()) return;
  String common = fits[0];
  for (const String& f : fits) {
    size_t n = 0;
    while (n < common.length() && n < f.length() && common[n] == f[n]) ++n;
    common = common.substring(0, n);
  }
  String add = common.substring(word.length());
  if (fits.size() == 1) add += ' ';
  if (!add.isEmpty()) {
    line = line.substring(0, cursor) + add + line.substring(cursor);
    cursor += add.length();
    redraw();
    return;
  }
  emit("\r\n");
  for (const String& f : fits) {
    emit(f);
    emit("   ");
  }
  emit("\r\n");
  drawPrompt();
}

// Enter: the typed line stays on screen above the next prompt, like a shell.
bool submit(String& out) {
  emit("\r\n");
  promptShown = false;
  out = line;
  trimSpaces(out);
  if (!out.isEmpty()) remember(out);
  line = "";
  cursor = 0;
  browsing = 0;
  draft = "";
  if (out.isEmpty()) {
    drawPrompt();
    return false;
  }
  return true;
}

void handleEscapeEnd(char c, const String& params) {
  const bool word = params.indexOf(';') >= 0;  // Option/Ctrl + arrow: "1;3D", "1;5C"
  switch (c) {
    case 'A': historyUp(); break;
    case 'B': historyDown(); break;
    case 'C': moveTo(word ? wordRight() : nextChar(cursor)); break;
    case 'D': moveTo(word ? wordLeft() : previousChar(cursor)); break;
    case 'H': moveTo(0); break;
    case 'F': moveTo(line.length()); break;
    case '~':
      if (params == "1" || params == "7") moveTo(0);
      if (params == "4" || params == "8") moveTo(line.length());
      if (params == "3") deleteForward();
      break;
    default: break;
  }
}

// One typed byte. Returns true when Enter finished a line.
bool handleKey(char c, String& out) {
  if (escape == Escape::Start) {
    escape = Escape::None;
    if (c == '[') {
      escape = Escape::Csi;
      escapeParams = "";
    } else if (c == 'O') {
      escape = Escape::Ss3;
    } else if (c == 'b') {
      moveTo(wordLeft());  // Option+Left in iTerm2 and Terminal
    } else if (c == 'f') {
      moveTo(wordRight());
    }
    return false;
  }
  if (escape == Escape::Csi) {
    if ((c >= '0' && c <= '9') || c == ';') {
      if (escapeParams.length() < 8) escapeParams += c;
      return false;
    }
    escape = Escape::None;
    handleEscapeEnd(c, escapeParams);
    return false;
  }
  if (escape == Escape::Ss3) {
    escape = Escape::None;
    handleEscapeEnd(c, "");
    return false;
  }

  const uint8_t byte = static_cast<uint8_t>(c);
  if (typedNeed > 0) {
    if (isContinuation(byte)) {
      typed[typedHave++] = c;
      if (typedHave == typedNeed) {
        insert(typed, typedNeed);
        typedNeed = 0;
      }
      return false;
    }
    typedNeed = 0;  // a broken character: drop it, then take this byte as usual
  }
  if (byte >= 0x80) {
    const size_t length = utf8Length(byte);
    if (length >= 2) {
      typed[0] = c;
      typedHave = 1;
      typedNeed = length;
    }
    return false;
  }
  if (c == kViewerHeartbeat) {
    if (heartbeat) heartbeat();
    return false;
  }
  const bool afterCr = lastWasCr;
  lastWasCr = c == '\r';
  switch (c) {
    case '\r': return submit(out);
    case '\n': return afterCr ? false : submit(out);
    case 8:
    case 127: backspace(); return false;
    case '\t': complete(); return false;
    case 27: escape = Escape::Start; return false;
    case 1: moveTo(0); return false;                 // Ctrl+A
    case 5: moveTo(line.length()); return false;     // Ctrl+E
    case 2: handleEscapeEnd('D', ""); return false;  // Ctrl+B
    case 6: handleEscapeEnd('C', ""); return false;  // Ctrl+F
    case 16: historyUp(); return false;              // Ctrl+P
    case 14: historyDown(); return false;            // Ctrl+N
    case 21: setLine(""); return false;              // Ctrl+U
    case 11: setLine(line.substring(0, cursor)); return false;  // Ctrl+K
    case 23: deleteWordBack(); return false;         // Ctrl+W
    case 12:                                         // Ctrl+L
      emit("\x1b[2J\x1b[H");
      drawPrompt();
      return false;
    case 3:  // Ctrl+C (the PlatformIO monitor keeps it to quit; other terminals send it)
      emit("^C\r\n");
      line = "";
      cursor = 0;
      browsing = 0;
      drawPrompt();
      return false;
    default:
      if (c >= 32 && c < 127) insert(&c, 1);
      return false;
  }
}

}  // namespace

void trimSpaces(String& text) {
  size_t start = 0, end = text.length();
  auto space = [](char c) { return c == ' ' || c == '\t' || c == '\r' || c == '\n'; };
  while (start < end && space(text[start])) ++start;
  while (end > start && space(text[end - 1])) --end;
  text = text.substring(start, end);
}

void consoleBegin() {
  if (mutex) return;
  mutex = xSemaphoreCreateRecursiveMutex();
  esp_log_set_vprintf(systemLog);
  esp_rom_install_channel_putc(1, romPutc);
}

void consoleStartPrompt() {
  ConsoleLock lock;  // draws the prompt on its way out
  promptOn = true;
}

void consoleSetPrompt(const String& newPrompt) {
  if (!mutex) {
    prompt = newPrompt;
    return;
  }
  xSemaphoreTakeRecursive(mutex, portMAX_DELAY);
  if (newPrompt != prompt) {
    prompt = newPrompt;
    if (promptShown) redraw();
  }
  xSemaphoreGiveRecursive(mutex);
}

void consoleSetCompleter(Completer c) { completer = c; }

void consoleSetHeartbeat(void (*handler)()) { heartbeat = handler; }

bool consoleReadLine(String& out) {
  if (!mutex) return false;
  printStaleLines();
  if (pendingLength > 0) {
    ConsoleLock lock;  // prints the lines that waited
  }
  while (Serial.available() > 0) {
    xSemaphoreTakeRecursive(mutex, portMAX_DELAY);
    const int c = Serial.read();
    if (promptOn && !promptShown && depth == 0) drawPrompt();
    const bool done = c >= 0 && handleKey(static_cast<char>(c), out);
    xSemaphoreGiveRecursive(mutex);
    if (done) return true;
  }
  return false;
}

ConsoleLock::ConsoleLock(bool quiet) : quiet_(quiet) {
  if (!mutex) return;
  taken_ = xSemaphoreTakeRecursive(mutex, portMAX_DELAY) == pdTRUE;
  if (taken_ && !quiet_) enter();
}

ConsoleLock::~ConsoleLock() {
  if (!taken_) return;
  if (!quiet_) {
    leave();
  } else if (depth == 0 && pendingLength > 0) {
    enter();  // lines that waited go above the prompt now
    leave();
  }
  xSemaphoreGiveRecursive(mutex);
}

void say(const char* format, ...) {
  ConsoleLock lock;
  va_list args;
  va_start(args, format);
  Serial.vprintf(format, args);
  va_end(args);
}
