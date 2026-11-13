// One kept-open connection to the server that answers scans: the detection
// server, or in LLM mode the model's server (pointLink in commands.cpp
// switches it).
//
// Opening an HTTPS connection costs DNS, a TCP round trip, a two-round-trip
// TLS 1.2 handshake and certificate checks done in software. From Hanoi to a
// US server that is over 1 s per scan, so the link opens ahead of time,
// stays open between scans, and reopens when the server closes it. A task of
// its own does the opening, so a slow or failed connection (it can take
// 40 s on weak Wi-Fi) never holds up typed commands.
#pragma once

#include <Arduino.h>

#include "config.h"

struct LinkTiming {
  bool reused = false;      // the scan found the connection already open
  uint32_t connectMs = 0;   // DNS + TCP + TLS, when it had to connect
  uint32_t sendMs = 0;      // handing the request to the network stack
  uint32_t waitMs = 0;      // until the first reply byte: upload, server, network
  uint32_t readMs = 0;      // rest of the reply
};

struct LinkReply {
  int status = 0;  // HTTP status, or 0 when the request failed
  String body;
  String error;
  LinkTiming timing;
};

struct LinkRequest {
  // Where the request goes. When it isn't where the link is, the link
  // switches there first, so a request never reaches a server it wasn't
  // meant for, even when the mode changed in the meantime.
  String url;
  const uint8_t* body = nullptr;
  size_t length = 0;
  const char* contentType = "";
  String headers;                        // extra header lines, each ending in \r\n
  const char* accept = nullptr;          // Accept header, when set
  size_t maxReplyBytes = MAX_REPLY_BYTES;
  uint32_t timeoutMs = HTTP_TIMEOUT_MS;  // from the end of sending to the end of the reply
};

// Starts the link task. Call in setup() before the other link functions.
void linkBegin();

// Checks the server address (https:// or http://). When it is good, the link
// task closes any open connection and connects to the new server. Returns at
// once; the [link] lines report the connection.
bool linkSetServer(const String& url, String& error);

// Checks an address the way linkSetServer does, without switching to it.
bool linkCheckUrl(const String& url, String& error);

// Closes the connection and keeps it closed until a server is set again.
void linkClearServer();

// Asks the link task to connect now instead of at its next retry, for
// example when Wi-Fi has just joined.
void linkConnectSoon();

bool linkConfigured();  // a server address is set
bool linkIsOpen();      // as of the link task's last check, at most 1 s ago

// POSTs the body and reads the reply, connecting first if needed. A reused
// connection that turns out to be dead is reopened once and the request sent
// again. Waits while the link task is connecting, then uses that connection.
LinkReply linkPost(const LinkRequest& request);
