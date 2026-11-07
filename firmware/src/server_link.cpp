#include "server_link.h"

#include <WiFi.h>
#include <WiFiClientSecure.h>

#include <atomic>

#include "ca_certs.h"
#include "config.h"
#include "console.h"

namespace {

struct Target {
  String host;
  String path = "/";
  uint16_t port = 443;
  bool https = true;
};

// One task at a time uses the connection: the link task to keep it open, or
// the worker to send a photo. Everything from here to the mutex is used only
// by whoever holds it.
Target target;
WiFiClientSecure secureClient;
WiFiClient plainClient;
bool wasOpen = false;
uint32_t openedAt = 0;
uint32_t nextAttemptAt = 0;
uint32_t retryDelayMs = LINK_RETRY_MIN_MS;
SemaphoreHandle_t linkMutex = nullptr;

// "server" stores the new address here; the mutex holder switches to it.
SemaphoreHandle_t pendingMutex = nullptr;
Target pendingTarget;
bool hasPending = false;

std::atomic<bool> configured{false};
std::atomic<bool> linkOpen{false};
std::atomic<bool> connectSoon{false};
TaskHandle_t linkTaskHandle = nullptr;

// Holds a FreeRTOS mutex until the end of the scope.
class Hold {
 public:
  Hold(SemaphoreHandle_t mutex, TickType_t wait) : mutex_(mutex), held_(xSemaphoreTake(mutex, wait) == pdTRUE) {}
  ~Hold() {
    if (held_) xSemaphoreGive(mutex_);
  }
  Hold(const Hold&) = delete;
  Hold& operator=(const Hold&) = delete;
  bool held() const { return held_; }

 private:
  SemaphoreHandle_t mutex_;
  bool held_;
};

WiFiClient& client() { return target.https ? static_cast<WiFiClient&>(secureClient) : plainClient; }

bool timeIsUp(uint32_t deadline) { return static_cast<int32_t>(millis() - deadline) >= 0; }

void scheduleRetry() {
  nextAttemptAt = millis() + retryDelayMs;
  retryDelayMs = min(retryDelayMs * 2, LINK_RETRY_MAX_MS);
}

bool parseUrl(const String& url, Target& out, String& error) {
  String rest;
  if (url.startsWith("https://")) {
    out.https = true;
    out.port = 443;
    rest = url.substring(8);
  } else if (url.startsWith("http://")) {
    out.https = false;
    out.port = 80;
    rest = url.substring(7);
  } else {
    error = "the address must start with https:// or http://";
    return false;
  }
  const int slash = rest.indexOf('/');
  String authority = slash < 0 ? rest : rest.substring(0, slash);
  out.path = slash < 0 ? String("/") : rest.substring(slash);
  const int colon = authority.indexOf(':');
  if (colon >= 0) {
    const long value = authority.substring(colon + 1).toInt();
    if (value <= 0 || value > 65535) {
      error = "bad port";
      return false;
    }
    out.port = static_cast<uint16_t>(value);
    authority = authority.substring(0, colon);
  }
  if (authority.isEmpty()) {
    error = "no host name";
    return false;
  }
  out.host = authority;
  return true;
}

// With linkMutex held: switches to the address "server" stored, if any.
void applyPendingServer() {
  Target next;
  bool changed = false;
  xSemaphoreTake(pendingMutex, portMAX_DELAY);
  if (hasPending) {
    next = pendingTarget;
    hasPending = false;
    changed = true;
  }
  xSemaphoreGive(pendingMutex);
  if (!changed) return;
  secureClient.stop();
  plainClient.stop();
  wasOpen = false;
  linkOpen = false;
  target = next;
  nextAttemptAt = millis();
  retryDelayMs = LINK_RETRY_MIN_MS;
}

bool openConnection(uint32_t& elapsedMs) {
  const uint32_t start = millis();
  IPAddress ip;
  if (!WiFi.hostByName(target.host.c_str(), ip)) {
    elapsedMs = millis() - start;
    say("[link] could not look up %s\n", target.host.c_str());
    return false;
  }
  const uint32_t dnsMs = millis() - start;
  bool ok;
  if (target.https) {
    secureClient.setHandshakeTimeout(TLS_HANDSHAKE_TIMEOUT_S);
    ok = secureClient.connect(ip, target.port, target.host.c_str(), kRootCaPem, nullptr, nullptr);
  } else {
    ok = plainClient.connect(ip, target.port, HTTP_CONNECT_TIMEOUT_MS);
  }
  elapsedMs = millis() - start;
  if (!ok) {
    char reason[96] = "";
    if (target.https) secureClient.lastError(reason, sizeof(reason));
    say("[link] could not connect to %s after %u ms %s\n", target.host.c_str(), static_cast<unsigned>(elapsedMs),
        reason);
    return false;
  }
  say("[link] connected to %s in %u ms (DNS %u ms, TCP%s %u ms)\n", target.host.c_str(),
      static_cast<unsigned>(elapsedMs), static_cast<unsigned>(dnsMs), target.https ? " + TLS" : "",
      static_cast<unsigned>(elapsedMs - dnsMs));
  wasOpen = true;
  linkOpen = true;
  openedAt = millis();
  return true;
}

bool writeAll(WiFiClient& c, const uint8_t* data, size_t length) {
  size_t sent = 0;
  while (sent < length) {
    const size_t chunk = min(length - sent, static_cast<size_t>(16384));
    const size_t n = c.write(data + sent, chunk);
    if (n == 0) return false;
    sent += n;
  }
  return true;
}

// One byte, waiting until the deadline: -1 when closed, -2 on timeout.
int readByte(WiFiClient& c, uint32_t deadline) {
  while (true) {
    if (c.available() > 0) return c.read();
    if (!c.connected()) return -1;
    if (timeIsUp(deadline)) return -2;
    delay(1);
  }
}

bool readLine(WiFiClient& c, uint32_t deadline, String& line) {
  line = "";
  while (true) {
    const int b = readByte(c, deadline);
    if (b < 0) return false;
    if (b == '\n') break;
    if (b != '\r' && line.length() < 512) line += static_cast<char>(b);
  }
  return true;
}

bool readBody(WiFiClient& c, uint32_t deadline, size_t length, String& body) {
  if (length > MAX_REPLY_BYTES) return false;
  body.reserve(length);
  uint8_t buffer[512];
  while (length > 0) {
    if (c.available() <= 0) {
      if (!c.connected() || timeIsUp(deadline)) return false;
      delay(1);
      continue;
    }
    const int n = c.read(buffer, min(length, sizeof(buffer)));
    if (n <= 0) return false;
    body.concat(reinterpret_cast<const char*>(buffer), static_cast<unsigned>(n));
    length -= static_cast<size_t>(n);
  }
  return true;
}

bool readChunkedBody(WiFiClient& c, uint32_t deadline, String& body) {
  String line;
  while (true) {
    if (!readLine(c, deadline, line)) return false;
    const long size = strtol(line.c_str(), nullptr, 16);
    if (size < 0 || body.length() + static_cast<size_t>(size) > MAX_REPLY_BYTES) return false;
    if (size == 0) return readLine(c, deadline, line);  // the blank line after the last chunk
    String chunk;
    if (!readBody(c, deadline, static_cast<size_t>(size), chunk)) return false;
    body += chunk;
    if (!readLine(c, deadline, line)) return false;
  }
}

enum class Outcome { Done, DeadBeforeReply, Failed };

Outcome exchange(const uint8_t* body, size_t length, const char* contentType, LinkReply& reply) {
  WiFiClient& c = client();
  String header = "POST " + target.path + " HTTP/1.1\r\nHost: " + target.host;
  if ((target.https && target.port != 443) || (!target.https && target.port != 80)) {
    header += ":" + String(target.port);
  }
  header += "\r\nUser-Agent: aware-bin/" FIRMWARE_VERSION "\r\nX-Bin-Token: " BIN_TOKEN "\r\nContent-Type: ";
  header += contentType;
  header += "\r\nContent-Length: " + String(length) + "\r\nConnection: keep-alive\r\n\r\n";

  // Header and body go out in one write, so the header doesn't travel as a
  // tiny packet of its own.
  const uint32_t sendStart = millis();
  const size_t total = header.length() + length;
  uint8_t* request = static_cast<uint8_t*>(psramFound() ? ps_malloc(total) : malloc(total));
  bool sent;
  if (request) {
    memcpy(request, header.c_str(), header.length());
    memcpy(request + header.length(), body, length);
    sent = writeAll(c, request, total);
    free(request);
  } else {
    sent = writeAll(c, reinterpret_cast<const uint8_t*>(header.c_str()), header.length()) &&
           writeAll(c, body, length);
  }
  reply.timing.sendMs = millis() - sendStart;
  if (!sent) {
    reply.error = "the connection closed while sending";
    return Outcome::DeadBeforeReply;
  }

  const uint32_t waitStart = millis();
  const uint32_t deadline = waitStart + HTTP_TIMEOUT_MS;
  while (c.available() <= 0) {
    if (!c.connected()) {
      reply.error = "the server closed the connection without replying";
      return Outcome::DeadBeforeReply;
    }
    if (timeIsUp(deadline)) {
      reply.error = "no reply within " + String(HTTP_TIMEOUT_MS / 1000) + " s";
      return Outcome::Failed;
    }
    delay(1);
  }
  reply.timing.waitMs = millis() - waitStart;

  const uint32_t readStart = millis();
  String line;
  if (!readLine(c, deadline, line) || !line.startsWith("HTTP/1.")) {
    reply.error = "bad status line: " + line.substring(0, 60);
    return Outcome::Failed;
  }
  const int status = line.substring(9, 12).toInt();
  long contentLength = -1;
  bool chunked = false;
  bool closeAfter = false;
  while (true) {
    if (!readLine(c, deadline, line)) {
      reply.error = "the reply headers were cut off";
      return Outcome::Failed;
    }
    if (line.isEmpty()) break;
    String lower = line;
    lower.toLowerCase();
    if (lower.startsWith("content-length:")) contentLength = lower.substring(15).toInt();
    if (lower.startsWith("transfer-encoding:") && lower.indexOf("chunked") >= 0) chunked = true;
    if (lower.startsWith("connection:") && lower.indexOf("close") >= 0) closeAfter = true;
  }
  bool bodyOk;
  if (chunked) {
    bodyOk = readChunkedBody(c, deadline, reply.body);
  } else if (contentLength >= 0) {
    bodyOk = readBody(c, deadline, static_cast<size_t>(contentLength), reply.body);
  } else {
    reply.error = "the reply has no length";
    return Outcome::Failed;
  }
  reply.timing.readMs = millis() - readStart;
  if (!bodyOk) {
    reply.error = "the reply body was cut off or too long";
    return Outcome::Failed;
  }
  reply.status = status;
  if (closeAfter) c.stop();
  return Outcome::Done;
}

// Notices a connection the server closed and reopens it, waiting longer
// after each failure. Skips the check while a scan is using the connection.
void maintain() {
  Hold hold(linkMutex, 0);
  if (!hold.held()) return;
  applyPendingServer();
  if (connectSoon.exchange(false)) {
    nextAttemptAt = millis();
    retryDelayMs = LINK_RETRY_MIN_MS;
  }
  if (!configured) return;
  const bool connected = client().connected();
  linkOpen = connected;
  if (connected || WiFi.status() != WL_CONNECTED) return;
  if (wasOpen) {
    say("[link] the server closed the connection after %u s; reopening\n",
        static_cast<unsigned>((millis() - openedAt) / 1000));
    wasOpen = false;
  }
  if (!timeIsUp(nextAttemptAt)) return;
  uint32_t ms = 0;
  if (openConnection(ms)) {
    retryDelayMs = LINK_RETRY_MIN_MS;
  } else {
    scheduleRetry();
  }
}

void linkTask(void*) {
  for (;;) {
    maintain();
    ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(LINK_CHECK_INTERVAL_MS));  // linkConnectSoon wakes it early
  }
}

}  // namespace

void linkBegin() {
  if (linkTaskHandle) return;
  linkMutex = xSemaphoreCreateMutex();
  pendingMutex = xSemaphoreCreateMutex();
  xTaskCreatePinnedToCore(linkTask, "bin-link", LINK_TASK_STACK_BYTES, nullptr, 1, &linkTaskHandle, xPortGetCoreID());
}

bool linkSetServer(const String& url, String& error) {
  linkBegin();  // in case setup() changes order: the mutexes must exist
  Target next;
  if (!parseUrl(url, next, error)) return false;
  xSemaphoreTake(pendingMutex, portMAX_DELAY);
  pendingTarget = next;
  hasPending = true;
  xSemaphoreGive(pendingMutex);
  configured = true;
  linkConnectSoon();
  return true;
}

void linkConnectSoon() {
  connectSoon = true;
  if (linkTaskHandle) xTaskNotifyGive(linkTaskHandle);
}

bool linkConfigured() { return configured; }

bool linkIsOpen() { return configured && linkOpen; }

LinkReply linkPost(const uint8_t* body, size_t length, const char* contentType) {
  LinkReply reply;
  Hold hold(linkMutex, portMAX_DELAY);
  applyPendingServer();
  if (!configured) {
    reply.error = "no server set";
    return reply;
  }
  for (int attempt = 0; attempt < 2; ++attempt) {
    reply = LinkReply();
    const bool reused = client().connected();
    reply.timing.reused = reused;
    if (!reused) {
      uint32_t ms = 0;
      if (!openConnection(ms)) {
        reply.error = "could not connect";
        linkOpen = false;
        scheduleRetry();
        return reply;
      }
      reply.timing.connectMs = ms;
    }
    const Outcome outcome = exchange(body, length, contentType, reply);
    if (outcome == Outcome::Done) {
      retryDelayMs = LINK_RETRY_MIN_MS;
      linkOpen = client().connected();
      return reply;
    }
    client().stop();
    wasOpen = false;
    linkOpen = false;
    if (outcome == Outcome::DeadBeforeReply && reused && attempt == 0) {
      say("[link] the kept-open connection was dead; reconnecting and sending again\n");
      continue;
    }
    return reply;
  }
  return reply;
}
