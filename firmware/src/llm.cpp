#include "llm.h"

#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>

#include <atomic>
#include <ctime>
#include <memory>

#include "ca_certs.h"
#include "config.h"
#include "console.h"
#include "llm_request.h"
#include "mbedtls/base64.h"

namespace {

constexpr const char* kDeviceUrl = "https://" OPENAI_AUTH_HOST "/codex/device";
constexpr const char* kDeviceCallback = "https://" OPENAI_AUTH_HOST "/deviceauth/callback";
constexpr uint32_t kRenewRetryMinMs = 60000;
constexpr uint32_t kRenewRetryMaxMs = 30 * 60000;

// The sign-in. The console reads it for "status", the worker for each
// request, and the sign-in task changes it. Used only with signInMutex held.
struct SignIn {
  String access;
  String refresh;
  String account;        // the ChatGPT account (workspace) the token is for
  String email;
  long long expiresAt = 0;  // the access token's exp, in Unix seconds
};
SignIn signIn;
String waitingCode;  // the code "llm login" waits for someone to enter
SemaphoreHandle_t signInMutex = nullptr;

struct Locked {
  Locked() { xSemaphoreTake(signInMutex, portMAX_DELAY); }
  ~Locked() { xSemaphoreGive(signInMutex); }
  Locked(const Locked&) = delete;
  Locked& operator=(const Locked&) = delete;
};

std::atomic<bool> loginWanted{false};
std::atomic<bool> loginBusy{false};  // from "llm login" until the sign-in ends
std::atomic<bool> logoutWanted{false};
std::atomic<bool> renewWanted{false};
TaskHandle_t taskHandle = nullptr;
String sessionId;  // one per start, sent like Codex's session-id

// Sign-in task only (and llmBegin, before the task starts).
Preferences store;
bool renewFailed = false;
uint32_t renewFailedAt = 0;
uint32_t renewRetryMs = kRenewRetryMinMs;

bool clockSet() { return time(nullptr) > 1700000000; }

String clip(String text) {
  text.replace("\n", " ");
  return text.length() > 160 ? text.substring(0, 160) + "..." : text;
}

String formEncode(const String& value) {
  String out;
  for (size_t i = 0; i < value.length(); ++i) {
    const char c = value[i];
    if (isalnum(static_cast<unsigned char>(c)) || c == '-' || c == '_' || c == '.' || c == '~') {
      out += c;
    } else {
      char escaped[4];
      snprintf(escaped, sizeof(escaped), "%%%02X", static_cast<unsigned char>(c));
      out += escaped;
    }
  }
  return out;
}

String jsonText(JsonVariantConst value) { return value.is<const char*>() ? String(value.as<const char*>()) : String(); }

// The claims in a JWT's middle part.
bool readClaims(const String& jwt, JsonDocument& claims) {
  const int first = jwt.indexOf('.');
  const int second = jwt.indexOf('.', first + 1);
  if (first < 0 || second < 0) return false;
  String payload = jwt.substring(first + 1, second);
  payload.replace('-', '+');
  payload.replace('_', '/');
  while (payload.length() % 4) payload += '=';
  const size_t capacity = payload.length() * 3 / 4 + 1;
  std::unique_ptr<uint8_t[]> decoded(new (std::nothrow) uint8_t[capacity]);
  size_t length = 0;
  if (!decoded || mbedtls_base64_decode(decoded.get(), capacity, &length,
                                        reinterpret_cast<const uint8_t*>(payload.c_str()), payload.length()) != 0) {
    return false;
  }
  return !deserializeJson(claims, reinterpret_cast<const char*>(decoded.get()), length);
}

long long expiryOf(const String& access) {
  JsonDocument claims;
  return readClaims(access, claims) ? claims["exp"].as<long long>() : 0;
}

String durationText(long long seconds) {
  if (seconds >= 2 * 86400) return String(static_cast<long>(seconds / 86400)) + " days";
  if (seconds >= 2 * 3600) return String(static_cast<long>(seconds / 3600)) + " hours";
  return String(static_cast<long>(seconds / 60)) + " min";
}

void forget() {
  {
    Locked lock;
    signIn = SignIn();
  }
  store.clear();
}

// Saves the tokens in an /oauth/token reply and starts using them. A reply
// without a new renewal token keeps the old one.
bool takeTokens(const String& reply, String& error) {
  JsonDocument doc;
  if (deserializeJson(doc, reply)) {
    error = "the reply is not JSON";
    return false;
  }
  SignIn next;
  next.access = jsonText(doc["access_token"]);
  next.refresh = jsonText(doc["refresh_token"]);
  JsonDocument claims;
  if (next.access.isEmpty() || !readClaims(next.access, claims)) {
    error = "the reply has no readable access token";
    return false;
  }
  next.account = jsonText(claims["https://api.openai.com/auth"]["chatgpt_account_id"]);
  next.expiresAt = claims["exp"].as<long long>();
  JsonDocument idClaims;
  if (readClaims(jsonText(doc["id_token"]), idClaims)) next.email = jsonText(idClaims["email"]);
  {
    Locked lock;
    if (next.refresh.isEmpty()) next.refresh = signIn.refresh;
    if (next.email.isEmpty()) next.email = signIn.email;
  }
  if (next.refresh.isEmpty()) {
    error = "the reply has no renewal token";
    return false;
  }
  // The renewal token first: the old one no longer works.
  if (!store.putString("refresh", next.refresh) || !store.putString("access", next.access)) {
    error = "could not save the tokens on the board";
    return false;
  }
  store.putString("account", next.account);
  store.putString("email", next.email);
  Locked lock;
  signIn = next;
  return true;
}

void load() {
  store.begin("awarellm", false);
  SignIn saved;
  auto get = [](const char* key) { return store.isKey(key) ? store.getString(key, "") : String(); };
  saved.access = get("access");
  saved.refresh = get("refresh");
  saved.account = get("account");
  saved.email = get("email");
  saved.expiresAt = expiryOf(saved.access);
  Locked lock;
  signIn = saved;
}

// One POST to auth.openai.com on a connection of its own (sign-in is rare,
// so it isn't kept open). Returns the HTTP status, or a negative HTTPClient
// error with its text in reply.
int authPost(const char* path, const char* contentType, const String& body, String& reply) {
  WiFiClientSecure tls;
  tls.setCACert(kRootCaPem);
  tls.setHandshakeTimeout(TLS_HANDSHAKE_TIMEOUT_S);
  HTTPClient http;
  http.setConnectTimeout(HTTP_CONNECT_TIMEOUT_MS);
  http.setTimeout(30000);
  http.setUserAgent("aware-bin/" FIRMWARE_VERSION);
  if (!http.begin(tls, String("https://" OPENAI_AUTH_HOST) + path)) {
    reply = "bad address";
    return HTTPC_ERROR_CONNECTION_REFUSED;
  }
  http.addHeader("Content-Type", contentType);
  const int status = http.POST(body);
  reply = status > 0 ? http.getString() : HTTPClient::errorToString(status);
  http.end();
  return status;
}

void endLogin() {
  {
    Locked lock;
    waitingCode = "";
  }
  loginBusy = false;
}

// The device-code sign-in of OpenAI's Codex CLI: ask for a code, show it,
// wait until someone enters it, then trade it for tokens.
void deviceLogin() {
  String reply;
  int status = authPost("/api/accounts/deviceauth/usercode", "application/json",
                        "{\"client_id\":\"" CODEX_CLIENT_ID "\"}", reply);
  JsonDocument doc;
  if (status != 200 || deserializeJson(doc, reply)) {
    say("[llm] could not start the sign-in (%d): %s\n", status, clip(reply).c_str());
    return endLogin();
  }
  const String deviceAuthId = jsonText(doc["device_auth_id"]);
  String code = jsonText(doc["user_code"]);
  if (code.isEmpty()) code = jsonText(doc["usercode"]);
  int interval = doc["interval"].is<const char*>() ? atoi(doc["interval"].as<const char*>()) : (doc["interval"] | 5);
  interval = constrain(interval, 1, 30);
  if (deviceAuthId.isEmpty() || code.isEmpty()) {
    say("[llm] could not start the sign-in: the reply has no code\n");
    return endLogin();
  }
  {
    Locked lock;
    waitingCode = code;
  }
  say("[llm] To sign the bin in to ChatGPT, open %s and enter the code %s (it works for 15 minutes)\n", kDeviceUrl,
      code.c_str());

  JsonDocument poll;
  poll["device_auth_id"] = deviceAuthId;
  poll["user_code"] = code;
  String pollBody;
  serializeJson(poll, pollBody);
  const uint32_t started = millis();
  while (millis() - started < LLM_LOGIN_TIMEOUT_MS) {
    ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(interval * 1000));
    if (logoutWanted) {
      say("[llm] sign-in stopped\n");
      return endLogin();
    }
    if (WiFi.status() != WL_CONNECTED) continue;
    status = authPost("/api/accounts/deviceauth/token", "application/json", pollBody, reply);
    if (status == 403 || status == 404 || status < 0) continue;  // not entered yet, or a network hiccup
    doc.clear();
    if (status != 200 || deserializeJson(doc, reply)) {
      say("[llm] the sign-in failed (%d): %s\n", status, clip(reply).c_str());
      return endLogin();
    }
    const String form = "grant_type=authorization_code&code=" + formEncode(jsonText(doc["authorization_code"])) +
                        "&redirect_uri=" + formEncode(kDeviceCallback) + "&client_id=" CODEX_CLIENT_ID +
                        "&code_verifier=" + formEncode(jsonText(doc["code_verifier"]));
    status = authPost("/oauth/token", "application/x-www-form-urlencoded", form, reply);
    String error;
    if (status != 200) {
      say("[llm] the sign-in failed at the last step (%d): %s\n", status, clip(reply).c_str());
    } else if (!takeTokens(reply, error)) {
      say("[llm] the sign-in failed: %s\n", error.c_str());
    } else {
      renewFailed = false;
      renewRetryMs = kRenewRetryMinMs;
      String email;
      {
        Locked lock;
        email = signIn.email;
      }
      say("[llm] signed in%s%s. \"mode llm\" sorts with the model.\n", email.isEmpty() ? "" : " as ", email.c_str());
    }
    return endLogin();
  }
  say("[llm] nobody entered the code within 15 minutes. Type \"llm login\" to try again.\n");
  endLogin();
}

// Trades the renewal token for new tokens. A refused renewal token (used up,
// revoked or expired) needs a new sign-in; other failures are tried again
// later, waiting longer each time.
void renew() {
  String refresh;
  {
    Locked lock;
    refresh = signIn.refresh;
  }
  if (refresh.isEmpty()) return;
  const String form = "grant_type=refresh_token&refresh_token=" + formEncode(refresh) + "&client_id=" CODEX_CLIENT_ID;
  String reply;
  const int status = authPost("/oauth/token", "application/x-www-form-urlencoded", form, reply);
  String error;
  if (status == 200 && takeTokens(reply, error)) {
    renewFailed = false;
    renewRetryMs = kRenewRetryMinMs;
    long long left;
    {
      Locked lock;
      left = signIn.expiresAt - time(nullptr);
    }
    say("[llm] renewed the ChatGPT sign-in%s\n", clockSet() ? (", good for " + durationText(left)).c_str() : "");
    return;
  }
  if (status == 401 || (status == 400 && (reply.indexOf("invalid_grant") >= 0 || reply.indexOf("refresh_token_") >= 0))) {
    forget();
    say("[llm] ChatGPT ended the bin's sign-in (%d: %s). Type \"llm login\" to sign in again.\n", status,
        clip(reply).c_str());
    return;
  }
  renewFailed = true;
  renewFailedAt = millis();
  say("[llm] could not renew the ChatGPT sign-in (%d: %s); trying again in %u min\n", status,
      clip(error.isEmpty() ? reply : error).c_str(), static_cast<unsigned>(renewRetryMs / 60000));
  renewRetryMs = min(renewRetryMs * 2, kRenewRetryMaxMs);
}

bool renewDue() {
  if (renewFailed && millis() - renewFailedAt < renewRetryMs) return false;
  Locked lock;
  return !signIn.refresh.isEmpty() && clockSet() && signIn.expiresAt - time(nullptr) < LLM_REFRESH_AHEAD_S;
}

void signInTask(void*) {
  for (;;) {
    if (logoutWanted.exchange(false)) forget();
    if (loginWanted.exchange(false)) {
      deviceLogin();
      continue;
    }
    if (WiFi.status() == WL_CONNECTED && (renewWanted.exchange(false) || renewDue())) renew();
    ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(LLM_AUTH_CHECK_MS));
  }
}

void wakeTask() {
  if (taskHandle) xTaskNotifyGive(taskHandle);
}

}  // namespace

void llmBegin() {
  if (taskHandle) return;
  signInMutex = xSemaphoreCreateMutex();
  char id[24];
  snprintf(id, sizeof(id), "aware-bin-%08lx", static_cast<unsigned long>(esp_random()));
  sessionId = id;
  load();
  xTaskCreatePinnedToCore(signInTask, "bin-llm", LLM_AUTH_TASK_STACK_BYTES, nullptr, 1, &taskHandle, xPortGetCoreID());
}

void llmLogin() {
  {
    Locked lock;
    if (!waitingCode.isEmpty()) {
      say("[llm] still waiting: open %s and enter the code %s\n", kDeviceUrl, waitingCode.c_str());
      return;
    }
  }
  if (loginBusy.exchange(true)) {
    say("[llm] already asking ChatGPT for a sign-in code\n");
    return;
  }
  logoutWanted = false;
  loginWanted = true;
  say("[llm] asking ChatGPT for a sign-in code\n");
  wakeTask();
}

void llmLogout() {
  {
    Locked lock;
    signIn = SignIn();
  }
  loginWanted = false;
  logoutWanted = true;
  wakeTask();
}

void llmRenewSoon() {
  renewWanted = true;
  wakeTask();
}

bool llmSignedIn() {
  Locked lock;
  return !signIn.access.isEmpty();
}

String llmSignInText() {
  Locked lock;
  if (!waitingCode.isEmpty()) return "waiting for the code " + waitingCode + " at " + kDeviceUrl;
  if (signIn.access.isEmpty()) return loginBusy ? "starting the sign-in" : "not signed in (type \"llm login\")";
  String text = "signed in";
  if (!signIn.email.isEmpty()) text += " as " + signIn.email;
  if (clockSet() && signIn.expiresAt) {
    const long long left = signIn.expiresAt - time(nullptr);
    text += left > 0 ? ", token good for " + durationText(left) : String(", token expired (renewing)");
  }
  return text;
}

bool llmBuildRequest(const uint8_t* jpeg, size_t length, const String& model, LlmRequest& out, String& error) {
  {
    Locked lock;
    if (signIn.access.isEmpty()) {
      error = "not signed in to ChatGPT: type \"llm login\"";
      return false;
    }
    out.headers = "Authorization: Bearer " + signIn.access + "\r\n";
    if (!signIn.account.isEmpty()) out.headers += "ChatGPT-Account-ID: " + signIn.account + "\r\n";
  }
  out.headers += "originator: aware_bin\r\nsession-id: " + sessionId + "\r\n";

  const std::string json = llm::requestJson(model.c_str(), LLM_REASONING_EFFORT, LLM_IMAGE_DETAIL);
  const size_t mark = json.find(llm::kPhotoMark);
  if (json.empty() || mark == std::string::npos) {
    error = "out of memory for the request";
    return false;
  }

  const size_t prefix = mark;
  const size_t encoded = 4 * ((length + 2) / 3);
  const size_t suffix = json.size() - prefix - strlen(llm::kPhotoMark);
  out.length = prefix + encoded + suffix;
  // +1: the base64 encoder ends with a NUL, which the suffix then covers.
  out.data = static_cast<uint8_t*>(psramFound() ? ps_malloc(out.length + 1) : malloc(out.length + 1));
  if (!out.data) {
    error = "out of memory for the request";
    return false;
  }
  memcpy(out.data, json.data(), prefix);
  size_t written = 0;
  if (mbedtls_base64_encode(out.data + prefix, encoded + 1, &written, jpeg, length) != 0 || written != encoded) {
    error = "could not encode the photo";
    return false;
  }
  memcpy(out.data + prefix + encoded, json.data() + prefix + strlen(llm::kPhotoMark), suffix);
  return true;
}
