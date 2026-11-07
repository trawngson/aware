// One kept-open connection to the detection server.
//
// Opening an HTTPS connection costs DNS, a TCP round trip, a two-round-trip
// TLS 1.2 handshake and certificate checks done in software. From Hanoi to a
// US server that is over 1 s per scan, so the link opens ahead of time,
// stays open between scans, and reopens in the background when the server
// closes it.
#pragma once

#include <Arduino.h>

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

// Sets the server address (https:// or http://); closes any open connection.
bool linkSetServer(const String& url, String& error);

// Opens the connection now if it is closed. Returns true when open.
bool linkConnect();

// Call from loop(): notices a connection the server closed and reopens it,
// waiting longer after each failure.
void linkMaintain();

bool linkIsOpen();
void linkClose();

// POSTs the body and reads the reply on the open connection, connecting
// first if needed. A reused connection that turns out to be dead is
// reopened once and the request sent again.
LinkReply linkPost(const uint8_t* body, size_t length, const char* contentType);
