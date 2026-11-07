#include "server_link.h"

#include <WiFi.h>
#include <WiFiClientSecure.h>

#include "ca_certs.h"
#include "config.h"

namespace {

String host;
String path = "/";
uint16_t port = 443;
bool https = true;
bool configured = false;

WiFiClientSecure secureClient;
WiFiClient plainClient;

bool wasOpen = false;
uint32_t openedAt = 0;
uint32_t lastCheckAt = 0;
uint32_t nextAttemptAt = 0;
uint32_t retryDelayMs = LINK_RETRY_MIN_MS;

WiFiClient& client() { return https ? static_cast<WiFiClient&>(secureClient) : plainClient; }

bool timeIsUp(uint32_t deadline) { return static_cast<int32_t>(millis() - deadline) >= 0; }

void scheduleRetry() {
  nextAttemptAt = millis() + retryDelayMs;
  retryDelayMs = min(retryDelayMs * 2, LINK_RETRY_MAX_MS);
}

bool parseUrl(const String& url, String& error) {
  String rest;
  if (url.startsWith("https://")) {
    https = true;
    port = 443;
    rest = url.substring(8);
  } else if (url.startsWith("http://")) {
    https = false;
    port = 80;
    rest = url.substring(7);
  } else {
    error = "the address must start with https:// or http://";
    return false;
  }
  const int slash = rest.indexOf('/');
  String authority = slash < 0 ? rest : rest.substring(0, slash);
  path = slash < 0 ? String("/") : rest.substring(slash);
  const int colon = authority.indexOf(':');
  if (colon >= 0) {
    const long value = authority.substring(colon + 1).toInt();
    if (value <= 0 || value > 65535) {
      error = "bad port";
      return false;
    }
    port = static_cast<uint16_t>(value);
    authority = authority.substring(0, colon);
  }
  if (authority.isEmpty()) {
    error = "no host name";
    return false;
  }
  host = authority;
  return true;
}

bool openConnection(uint32_t& elapsedMs) {
  const uint32_t start = millis();
  IPAddress ip;
  if (!WiFi.hostByName(host.c_str(), ip)) {
    elapsedMs = millis() - start;
    Serial.printf("[link] could not look up %s\n", host.c_str());
    return false;
  }
  const uint32_t dnsMs = millis() - start;
  bool ok;
  if (https) {
    secureClient.setHandshakeTimeout(TLS_HANDSHAKE_TIMEOUT_S);
    ok = secureClient.connect(ip, port, host.c_str(), kRootCaPem, nullptr, nullptr);
  } else {
    ok = plainClient.connect(ip, port, HTTP_CONNECT_TIMEOUT_MS);
  }
  elapsedMs = millis() - start;
  if (!ok) {
    char reason[96] = "";
    if (https) secureClient.lastError(reason, sizeof(reason));
    Serial.printf("[link] could not connect to %s after %u ms %s\n", host.c_str(), static_cast<unsigned>(elapsedMs),
                  reason);
    return false;
  }
  Serial.printf("[link] connected to %s in %u ms (DNS %u ms, TCP%s %u ms)\n", host.c_str(),
                static_cast<unsigned>(elapsedMs), static_cast<unsigned>(dnsMs), https ? " + TLS" : "",
                static_cast<unsigned>(elapsedMs - dnsMs));
  wasOpen = true;
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
  String header = "POST " + path + " HTTP/1.1\r\nHost: " + host;
  if ((https && port != 443) || (!https && port != 80)) header += ":" + String(port);
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

}  // namespace

bool linkSetServer(const String& url, String& error) {
  linkClose();
  configured = parseUrl(url, error);
  nextAttemptAt = 0;
  retryDelayMs = LINK_RETRY_MIN_MS;
  return configured;
}

bool linkIsOpen() { return configured && client().connected(); }

void linkClose() {
  secureClient.stop();
  plainClient.stop();
  wasOpen = false;
}

bool linkConnect() {
  if (!configured || WiFi.status() != WL_CONNECTED) return false;
  if (client().connected()) return true;
  uint32_t ms = 0;
  if (openConnection(ms)) {
    retryDelayMs = LINK_RETRY_MIN_MS;
    return true;
  }
  scheduleRetry();
  return false;
}

void linkMaintain() {
  if (!configured || WiFi.status() != WL_CONNECTED) return;
  const uint32_t now = millis();
  if (now - lastCheckAt < LINK_CHECK_INTERVAL_MS) return;
  lastCheckAt = now;
  if (client().connected()) return;
  if (wasOpen) {
    Serial.printf("[link] the server closed the connection after %u s; reopening\n",
                  static_cast<unsigned>((now - openedAt) / 1000));
    wasOpen = false;
  }
  if (!timeIsUp(nextAttemptAt)) return;
  linkConnect();
}

LinkReply linkPost(const uint8_t* body, size_t length, const char* contentType) {
  LinkReply reply;
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
        scheduleRetry();
        return reply;
      }
      reply.timing.connectMs = ms;
    }
    const Outcome outcome = exchange(body, length, contentType, reply);
    if (outcome == Outcome::Done) {
      retryDelayMs = LINK_RETRY_MIN_MS;
      return reply;
    }
    client().stop();
    wasOpen = false;
    if (outcome == Outcome::DeadBeforeReply && reused && attempt == 0) {
      Serial.println("[link] the kept-open connection was dead; reconnecting and sending again");
      continue;
    }
    return reply;
  }
  return reply;
}
