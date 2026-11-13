#include "commands.h"

#include <WiFi.h>

#include <cstdarg>
#include <iterator>

#include "camera.h"
#include "config.h"
#include "console.h"
#include "imu.h"
#include "llm.h"
#include "plate_watch.h"
#include "server_link.h"
#include "settings.h"
#include "status_report.h"
#include "wifi_join.h"
#include "worker.h"

namespace {

bool lastCommandOk = true;  // the prompt's arrow turns red after a failed command

// Prints why a command didn't work; the prompt's arrow turns red.
void fail(const char* text, ...) __attribute__((format(printf, 1, 2)));
void fail(const char* text, ...) {
  lastCommandOk = false;
  ConsoleLock lock;
  va_list args;
  va_start(args, text);
  Serial.vprintf(text, args);
  va_end(args);
}

// queueWork, with the red arrow when the job was skipped.
void queue(const Work& work, const String& what) {
  if (!queueWork(work, what)) lastCommandOk = false;
}

const char* const kCommands[] = {
    "angle", "auto", "camera", "conf", "connect", "feed", "help", "imu", "llm", "mode",
#ifdef AWARE_SIMULATOR
    "photo", "photos",
#endif
    "pass", "quality", "reboot", "scan", "servo", "server", "snap", "speed", "ssid", "status", "txpower",
};

void printHelp() {
  say("Commands:\n"
      "  status                 the bin at a glance\n"
      "  ssid <name>            Wi-Fi network name (2.4 GHz)\n"
      "  pass <password>        Wi-Fi password (empty for an open network)\n"
      "  connect                join the Wi-Fi network\n"
      "  server <url>           detection server address (https:// or http://)\n"
      "  mode [yolo|llm]        who names the items: the detection server (yolo) or an LLM\n"
      "  llm login | logout     sign the board in to ChatGPT for llm mode, or forget it\n"
      "  llm model <name>       the model llm mode asks (default " LLM_DEFAULT_MODEL ")\n"
      "  llm                    the ChatGPT sign-in and model\n"
      "  conf <0.05-0.95>       lowest confidence routed to a recycling bin (yolo mode)\n"
      "  speed <0-1000>         servo speed in degrees a second (0: as fast as it goes)\n"
      "  quality <4-63>         camera JPEG quality; lower is sharper but slower to send\n"
      "  txpower <2-21>         Wi-Fi transmit power in dBm (19.5 is the most)\n"
      "  servo <0-180>          turn the servo now (test)\n"
      "  angle <name> <0-180>   set and show the angle for home, paper, plastic_bottles or other\n"
      "  snap                   take a photo and send it to the viewer (camera test)\n"
#ifdef AWARE_SIMULATOR
      "  photos                 list the simulator's photos\n"
      "  photo <n>              send photo n on the next scan\n"
#endif
      "  scan                   photo -> server or LLM -> servo (same as the BOOT button)\n"
      "  auto on|off            scan by itself when an item lands (on after every start)\n"
      "  camera on|off          stop or start the camera (to test whether it disturbs Wi-Fi)\n"
      "  feed [off]             open (or close) the live camera window on the Mac\n"
      "  imu                    the plate's tilt, shake and impacts (MPU-6050)\n"
      "  imu level              save the plate's tilt now as level (plate home and level)\n"
      "  imu on|off             use the IMU's checks, or ignore it (saved)\n"
      "  reboot                 restart the board\n"
      "Commands work at any time. scan, snap, servo and angle wait their turn\n"
      "while the camera or servo is busy.\n"
      "Keys: Up/Down history, Tab completes, Left/Right, Ctrl+A/E start/end,\n"
      "Ctrl+W deletes a word, Ctrl+U clears the line, Ctrl+L clears the screen.\n");
}

bool parseAngle(const String& text, int& angle) {
  if (text.isEmpty() || text.length() > 3) return false;
  for (size_t i = 0; i < text.length(); ++i) {
    if (!isDigit(text[i])) return false;
  }
  angle = text.toInt();
  return angle >= 0 && angle <= 180;
}

bool parseNumber(const String& text, int low, int high, int& value) {
  if (text.isEmpty() || text.length() > 4) return false;
  for (size_t i = 0; i < text.length(); ++i) {
    if (!isDigit(text[i])) return false;
  }
  value = text.toInt();
  return value >= low && value <= high;
}

// Model names: letters, digits, dots, dashes and underscores, as in gpt-6-luna.
bool validModelName(const String& name) {
  if (name.isEmpty() || name.length() > 48) return false;
  for (size_t i = 0; i < name.length(); ++i) {
    const char c = name[i];
    if (!isAlphaNumeric(c) && c != '.' && c != '-' && c != '_') return false;
  }
  return true;
}

void setAngle(const String& arg) {
  const int space = arg.indexOf(' ');
  const String name = space < 0 ? arg : arg.substring(0, space);
  String value = space < 0 ? String() : arg.substring(space + 1);
  trimSpaces(value);
  int angle = 0;
  Destination* d = settings::findDestination(name);
  if (!parseAngle(value, angle) || (!d && name != "home")) {
    fail("Usage: angle <home|paper|plastic_bottles|other> <0-180>\n");
    return;
  }
  if (!d) {
    settings::saveHomeAngle(angle);
    say("Home angle saved: %d\n", angle);
    queue({Job::Servo, angle}, "angle home");
    return;
  }
  settings::saveAngle(*d, angle);
  say("%s angle saved: %d. Showing it now.\n", d->stream, angle);
  queue({Job::ShowAngle, angle}, "angle " + name);
}

void setServer(String url) {
  while (url.endsWith("/")) url.remove(url.length() - 1);
  const bool valid = (url.startsWith("https://") && url.length() > 8) || (url.startsWith("http://") && url.length() > 7);
  if (!valid) {
    fail("Usage: server https://<address>\n");
    return;
  }
  String error;
  if (!linkCheckUrl(url, error)) {
    fail("Bad server address: %s\n", error.c_str());
    return;
  }
  settings::saveServerUrl(url);
  if (settings::mode == Mode::Llm) {
    say("Server saved: %s. Scans use it in yolo mode (\"mode yolo\"); now they go to the LLM.\n", url.c_str());
    return;
  }
  pointLink();
  say("Server saved: %s. Connecting in the background.\n", url.c_str());
}

void setMode(String arg) {
  arg.toLowerCase();
  if (arg.isEmpty()) {
    say("Mode: %s. \"mode yolo\" or \"mode llm\" changes it.\n", modeName(settings::mode));
    return;
  }
  if (arg != "yolo" && arg != "llm") {
    fail("Usage: mode yolo|llm\n");
    return;
  }
  settings::saveMode(arg == "llm" ? Mode::Llm : Mode::Yolo);
  pointLink();
  if (settings::mode == Mode::Yolo) {
    say("Mode saved: yolo. Scans go to the detection server%s.\n",
        settings::serverUrl.isEmpty() ? " once one is set (\"server <url>\")" : "");
  } else if (llmSignedIn()) {
    say("Mode saved: llm. Scans go to %s on ChatGPT; \"conf\" doesn't apply.\n", settings::llmModel.c_str());
  } else {
    say("Mode saved: llm. Sign the board in first: type \"llm login\".\n");
  }
}

void llmCommand(const String& arg) {
  const int space = arg.indexOf(' ');
  String sub = space < 0 ? arg : arg.substring(0, space);
  String value = space < 0 ? String() : arg.substring(space + 1);
  sub.toLowerCase();
  trimSpaces(value);
  if (sub.isEmpty()) {
    say("ChatGPT: %s\nModel: %s, reasoning " LLM_REASONING_EFFORT ", image detail " LLM_IMAGE_DETAIL
        "\nMode: %s\n",
        llmSignInText().c_str(), settings::llmModel.c_str(), modeName(settings::mode));
  } else if (sub == "login") {
    if (WiFi.status() != WL_CONNECTED) {
      fail("[llm] no Wi-Fi: type \"connect\" first\n");
      return;
    }
    llmLogin();
  } else if (sub == "logout") {
    llmLogout();
    say("[llm] the board forgot its ChatGPT sign-in\n");
  } else if (sub == "model" && value.isEmpty()) {
    say("Model: %s\n", settings::llmModel.c_str());
  } else if (sub == "model" && validModelName(value)) {
    settings::saveLlmModel(value);
    say("Model saved: %s\n", value.c_str());
  } else if (sub == "model") {
    fail("Usage: llm model <name>, for example llm model " LLM_DEFAULT_MODEL "\n");
  } else {
    fail("Usage: llm [login|logout|model <name>]\n");
  }
}

void setSpeed(const String& arg) {
  int value = 0;
  if (!parseNumber(arg, 0, 1000, value)) {
    fail("Usage: speed <0-1000>   (degrees a second; 0 = as fast as the servo goes)\n");
    return;
  }
  settings::saveServoSpeed(value);
  say("Servo speed saved: %d deg/s\n", value);
}

void setQuality(const String& arg) {
  int value = 0;
  if (!parseNumber(arg, 4, 63, value)) {
    fail("Usage: quality <4-63>   (lower is sharper and bigger)\n");
    return;
  }
  settings::saveJpegQuality(value);
  cameraSetQuality(value);
  say("JPEG quality saved: %d\n", value);
}

void setMinConfidence(const String& arg) {
  const float value = arg.toFloat();
  if (arg.isEmpty() || value < 0.05f || value > 0.95f) {
    fail("Usage: conf <0.05-0.95>\n");
    return;
  }
  settings::saveMinConfidence(value);
  say("Min confidence saved: %.2f\n", value);
}

void setTxPower(const String& arg) {
  const float value = arg.toFloat();
  if (arg.isEmpty() || value < 2 || value > 21) {
    fail("Usage: txpower <2-21>   (dBm; 19.5 is the most)\n");
    return;
  }
  settings::saveWifiTxDbm(value);
  applyTxPower();
  say("Wi-Fi transmit power saved: %.1f dBm (the radio uses %.1f)\n", value, txPowerNow());
}

void imuCommand(String arg) {
  arg.toLowerCase();
  if (arg.isEmpty()) {
    printImu();
  } else if (arg == "on" || arg == "off") {
    settings::saveImuOn(arg == "on");
    say("IMU %s (saved)%s\n", settings::imuOn ? "on: its checks apply" : "off: the bin ignores it",
        settings::imuOn && !imuPresent() ? ", once one is found" : "");
  } else if (arg == "level") {
    const float before = imuNow().tiltDeg;
    String why;
    if (!imuSaveLevel(why)) {
      fail("[imu] can't save the level: %s\n", why.c_str());
      return;
    }
    say("Level saved: the tilt reads from here now (it read %.1f° before)\n", before);
  } else {
    fail("Usage: imu [level|on|off]\n");
  }
}

}  // namespace

void pointLink() {
  String error;
  if (settings::mode == Mode::Llm) {
    linkSetServer(LLM_URL, error);
  } else if (!settings::serverUrl.isEmpty()) {
    linkSetServer(settings::serverUrl, error);
  } else {
    linkClearServer();
  }
  if (!error.isEmpty()) say("[link] bad server address: %s\n", error.c_str());
}

String buildPrompt() { return String(lastCommandOk ? "\x1b[1;32m" : "\x1b[1;31m") + "➜  \x1b[1;32maware-bin\x1b[0m "; }

void completeWords(const String& before, std::vector<const char*>& words) {
  const int space = before.indexOf(' ');
  if (space < 0) {
    words.assign(std::begin(kCommands), std::end(kCommands));
    return;
  }
  if (before.indexOf(' ', space + 1) >= 0) return;  // only the first two words
  String command = before.substring(0, space);
  command.toLowerCase();
  if (command == "angle") {
    words = {"home", "paper", "plastic_bottles", "other"};
  } else if (command == "imu") {
    words = {"level", "on", "off"};
  } else if (command == "auto" || command == "camera" || command == "feed") {
    words = {"on", "off"};
  } else if (command == "mode") {
    words = {"yolo", "llm"};
  } else if (command == "llm") {
    words = {"login", "logout", "model"};
  }
}

void handleCommand(String line) {
  lastCommandOk = true;
  trimSpaces(line);
  const int space = line.indexOf(' ');
  String cmd = space < 0 ? line : line.substring(0, space);
  String arg = space < 0 ? String() : line.substring(space + 1);
  cmd.toLowerCase();
  trimSpaces(arg);

  if (cmd == "help") {
    printHelp();
  } else if (cmd == "status") {
    printStatus();
  } else if (cmd == "ssid") {
    settings::saveWifiSsid(arg);
    say("Network saved: \"%s\". Now type \"pass <password>\", then \"connect\"\n", arg.c_str());
  } else if (cmd == "pass") {
    settings::saveWifiPass(arg);
    say("%s\n", arg.isEmpty() ? "Password cleared (open network)." : "Password saved. Type \"connect\"");
  } else if (cmd == "connect") {
    startJoin();
  } else if (cmd == "server") {
    setServer(arg);
  } else if (cmd == "mode") {
    setMode(arg);
  } else if (cmd == "llm") {
    llmCommand(arg);
  } else if (cmd == "conf") {
    setMinConfidence(arg);
  } else if (cmd == "speed") {
    setSpeed(arg);
  } else if (cmd == "txpower") {
    setTxPower(arg);
  } else if (cmd == "quality") {
    setQuality(arg);
  } else if (cmd == "servo") {
    int angle = 0;
    if (parseAngle(arg, angle)) {
      queue({Job::Servo, angle}, "servo " + arg);
    } else {
      fail("Usage: servo <0-180>\n");
    }
  } else if (cmd == "angle") {
    setAngle(arg);
  } else if (cmd == "snap") {
    queue({Job::Snap, 0}, "snap");
  } else if (cmd == "feed" && (arg.isEmpty() || arg == "on")) {
    // The PlatformIO monitor's aware_feed filter (monitor/filter_aware_feed.py)
    // sees this line and opens scripts/viewer.py, which then keeps the stream on.
    say(kLiveCamera ? "[feed] opening the live view on the Mac\n"
                    : "[feed] opening the live view on the Mac (the simulator has no live camera)\n");
  } else if (cmd == "feed" && arg == "off") {
    liveStop();
    say("[feed] closing the live view\n");
  } else if (cmd == "feed") {
    fail("Usage: feed [off]\n");
  } else if (cmd == "camera" && (arg == "on" || arg == "off")) {
    queue({arg == "on" ? Job::CameraOn : Job::CameraOff, 0}, "camera " + arg);
  } else if (cmd == "camera") {
    fail("Usage: camera on|off\n");
  } else if (cmd == "auto") {
    settings::autoScan = arg != "off";
    say("Automatic scans %s\n", settings::autoScan ? "on" : "off");
  } else if (cmd == "imu") {
    imuCommand(arg);
  } else if (cmd == "photos") {
    lastCommandOk = cameraListPhotos();
  } else if (cmd == "photo") {
    lastCommandOk = cameraChoosePhoto(arg.toInt());
  } else if (cmd == "scan") {
    if (!requestScan()) lastCommandOk = false;
  } else if (cmd == "reboot") {
    ESP.restart();
  } else {
    fail("Unknown command \"%s\". Type \"help\" for all commands.\n", cmd.c_str());
  }
}
