// LLM mode's sign-in and requests (README, LLM mode).
//
// In LLM mode the board sends the photo straight to an OpenAI model on the
// ChatGPT Codex backend (LLM_URL) and routes the items it lists. It signs in
// on its own, with the device-code flow of OpenAI's Codex CLI: "llm login"
// prints a code to type at auth.openai.com/codex/device. That gives the board
// a sign-in of its own, apart from the Mac's Codex: each renewal replaces the
// renewal token, so two programs sharing one sign-in would log each other
// out. The tokens are saved on the board (NVS, namespace "awarellm") and a
// task of its own renews them a day before they run out, so a scan never
// waits for the sign-in.
#pragma once

#include <Arduino.h>

// Loads the saved sign-in and starts the sign-in task. Call in setup().
void llmBegin();

// Starts the device-code sign-in in the background; [llm] lines say what to
// do. Replaces the current sign-in once the code is entered.
void llmLogin();

// Forgets the board's sign-in (and stops a sign-in that is waiting for its code).
void llmLogout();

// Renews the token now, for example after ChatGPT refused it.
void llmRenewSoon();

bool llmSignedIn();

// For "status" and "llm": who is signed in and for how long, or what the
// sign-in is waiting for.
String llmSignInText();

// One photo's request: the JSON body (in PSRAM) and the sign-in headers.
class LlmRequest {
 public:
  LlmRequest() = default;
  ~LlmRequest() { free(data); }
  LlmRequest(const LlmRequest&) = delete;
  LlmRequest& operator=(const LlmRequest&) = delete;

  uint8_t* data = nullptr;
  size_t length = 0;
  String headers;  // each line ends in \r\n
};

// Builds the request for one JPEG. False, with the reason, when the board
// isn't signed in or is out of memory.
bool llmBuildRequest(const uint8_t* jpeg, size_t length, const String& model, LlmRequest& out, String& error);
