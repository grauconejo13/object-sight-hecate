// Hecate wearable camera: ESP32-S3-EYE pushes JPEG frames to the backend.
//
// The camera rides on the phone's hotspot, so nothing can connect *to* it.
// Instead it POSTs each frame over HTTPS (verified Let's Encrypt cert + bearer
// token) and reads its settings back from the response headers, which the
// phone app edits. No open ports, no JSON library, nothing stored on-device.
//
// Arduino IDE: board "ESP32S3 Dev Module", PSRAM "OPI PSRAM",
// Flash 8MB (or your board's size), Partition Scheme with >= 3MB app.

#include <Arduino.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <WiFiMulti.h>

#include "esp_camera.h"
#include "root_ca.h"
#include "secrets.h"

// Pin map for CAMERA_MODEL_ESP32S3_EYE (identical to camera_pins.h in the
// CameraWebServer example that already worked with this board).
#define PWDN_GPIO_NUM -1
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 15
#define SIOD_GPIO_NUM 4
#define SIOC_GPIO_NUM 5
#define Y9_GPIO_NUM 16
#define Y8_GPIO_NUM 17
#define Y7_GPIO_NUM 18
#define Y6_GPIO_NUM 12
#define Y5_GPIO_NUM 10
#define Y4_GPIO_NUM 8
#define Y3_GPIO_NUM 9
#define Y2_GPIO_NUM 11
#define VSYNC_GPIO_NUM 6
#define HREF_GPIO_NUM 7
#define PCLK_GPIO_NUM 13

// Backends to try, in order. HECATE_BACKUP_URL is optional (define it in secrets.h).
// A backup only helps if the phone app reads from that same backend.
static const char *BASE_URLS[] = {
  HECATE_BASE_URL,
#ifdef HECATE_BACKUP_URL
  HECATE_BACKUP_URL,
#endif
};
static const size_t BASE_URL_COUNT = sizeof(BASE_URLS) / sizeof(BASE_URLS[0]);
static const uint8_t FAILURES_BEFORE_SWITCH = 3;
static const uint32_t DIAGNOSE_EVERY_MS = 30000;
static const char *AUTH_HEADER = "Bearer " HECATE_DEVICE_TOKEN;
static const uint32_t PAUSED_POLL_MS = 3000;
static const uint32_t MAX_BACKOFF_MS = 8000;

struct Settings {
  framesize_t frameSize = FRAMESIZE_VGA;
  int quality = 12;
  uint32_t intervalMs = 400;
  bool vflip = false;
  bool hmirror = false;
  bool paused = false;
};

WiFiMulti wifi;
WiFiClientSecure tls;
HTTPClient http;
Settings current;
uint32_t backoffMs = 0;
uint32_t framesSent = 0;
size_t activeUrl = 0;
uint8_t consecutiveFailures = 0;
uint32_t lastDiagnosisAt = 0;

const char *HEADER_KEYS[] = {
  "X-Hecate-Frame-Size", "X-Hecate-Quality", "X-Hecate-Interval-Ms",
  "X-Hecate-Vflip", "X-Hecate-Hmirror", "X-Hecate-Paused",
};

const char *frameSizeName(framesize_t size) {
  switch (size) {
    case FRAMESIZE_QVGA: return "QVGA";
    case FRAMESIZE_VGA: return "VGA";
    case FRAMESIZE_SVGA: return "SVGA";
    case FRAMESIZE_HD: return "HD";
    default: return "?";
  }
}

// Sent with every request so the phone app can confirm a change took effect.
String appliedHeader() {
  char buf[48];
  snprintf(buf, sizeof(buf), "%s;%d;%lu;%d;%d;%d", frameSizeName(current.frameSize), current.quality,
           (unsigned long)current.intervalMs, current.vflip, current.hmirror, current.paused);
  return String(buf);
}

framesize_t parseFrameSize(const String &name, framesize_t fallback) {
  if (name == "QVGA") return FRAMESIZE_QVGA;
  if (name == "VGA") return FRAMESIZE_VGA;
  if (name == "SVGA") return FRAMESIZE_SVGA;
  if (name == "HD") return FRAMESIZE_HD;
  return fallback;
}

void applySettings(const Settings &next) {
  sensor_t *sensor = esp_camera_sensor_get();
  if (!sensor) return;
  if (next.frameSize != current.frameSize) sensor->set_framesize(sensor, next.frameSize);
  if (next.quality != current.quality) sensor->set_quality(sensor, next.quality);
  if (next.vflip != current.vflip) sensor->set_vflip(sensor, next.vflip);
  if (next.hmirror != current.hmirror) sensor->set_hmirror(sensor, next.hmirror);
  bool changed = next.frameSize != current.frameSize || next.quality != current.quality ||
                 next.intervalMs != current.intervalMs || next.vflip != current.vflip ||
                 next.hmirror != current.hmirror || next.paused != current.paused;
  current = next;
  if (changed) Serial.printf("Settings applied: %s\n", appliedHeader().c_str());
}

// Settings arrive as response headers; missing or malformed values keep the current ones.
void readSettingsHeaders() {
  if (!http.hasHeader("X-Hecate-Paused")) {
    Serial.println("Response had no X-Hecate-* settings headers (check the Funnel path)");
    return;
  }
  Settings next = current;
  next.frameSize = parseFrameSize(http.header("X-Hecate-Frame-Size"), current.frameSize);
  int quality = http.header("X-Hecate-Quality").toInt();
  if (quality >= 8 && quality <= 40) next.quality = quality;
  long interval = http.header("X-Hecate-Interval-Ms").toInt();
  if (interval >= 100 && interval <= 5000) next.intervalMs = interval;
  next.vflip = http.header("X-Hecate-Vflip") == "1";
  next.hmirror = http.header("X-Hecate-Hmirror") == "1";
  next.paused = http.header("X-Hecate-Paused") == "1";
  applySettings(next);
}

bool startCamera() {
  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  // Allocate buffers for the largest size the app can choose, then drop to VGA.
  config.frame_size = FRAMESIZE_HD;
  config.jpeg_quality = current.quality;
  config.fb_count = 2;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.grab_mode = CAMERA_GRAB_LATEST;  // Always send the freshest frame.

  if (!psramFound()) {
    Serial.println("PSRAM not found: enable OPI PSRAM in Tools > PSRAM");
    config.frame_size = FRAMESIZE_VGA;
    config.fb_count = 1;
    config.fb_location = CAMERA_FB_IN_DRAM;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed: 0x%x\n", err);
    return false;
  }
  sensor_t *sensor = esp_camera_sensor_get();
  sensor->set_framesize(sensor, current.frameSize);
  return true;
}

void connectWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.print("Joining Wi-Fi");
  uint32_t started = millis();
  while (wifi.run(5000) != WL_CONNECTED) {
    Serial.print('.');
    if (millis() - started > 60000) {
      Serial.println("\nNo Wi-Fi for 60 s, restarting");
      ESP.restart();
    }
  }
  Serial.printf("\nConnected to %s, IP %s\n", WiFi.SSID().c_str(), WiFi.localIP().toString().c_str());
}

// Split "https://host:port" into host and port (default 443).
bool parseBase(const char *base, String &host, uint16_t &port) {
  String url(base);
  if (!url.startsWith("https://")) return false;
  url = url.substring(8);
  int slash = url.indexOf('/');
  if (slash >= 0) url = url.substring(0, slash);
  int colon = url.indexOf(':');
  host = colon >= 0 ? url.substring(0, colon) : url;
  port = colon >= 0 ? (uint16_t)url.substring(colon + 1).toInt() : 443;
  return host.length() > 0 && port > 0;
}

// HTTPClient reports DNS, TCP and TLS failures all as "-1 connection refused".
// Test each stage separately so the Serial Monitor says which one fails.
void diagnose(const char *base) {
  lastDiagnosisAt = millis();
  String host;
  uint16_t port;
  Serial.printf("--- Checking %s\n", base);
  if (!parseBase(base, host, port)) {
    Serial.println("  URL: INVALID (expected https://host:port, no trailing path)");
    return;
  }
  Serial.printf("  Wi-Fi: %s, IP %s, DNS %s\n", WiFi.SSID().c_str(), WiFi.localIP().toString().c_str(),
                WiFi.dnsIP().toString().c_str());

  // Hotspots answer DNS themselves, so a working lookup doesn't prove internet access.
  // A plain TCP connection to a well-known public server does.
  {
    WiFiClient net;
    bool online = net.connect(IPAddress(1, 1, 1, 1), 443, 6000);
    net.stop();
    Serial.println(online ? "  Internet: ok (reached 1.1.1.1:443)"
                          : "  Internet: FAILED to reach 1.1.1.1:443. This network gives the camera no internet "
                            "(check the hotspot's data / tethering plan).");
  }

  IPAddress ip;
  // Some cores report success with 0.0.0.0 when the name doesn't exist.
  if (!WiFi.hostByName(host.c_str(), ip) || ip == IPAddress(0, 0, 0, 0)) {
    Serial.printf("  DNS:  FAILED for %s. Not publicly resolvable: Funnel is off for this host, "
                  "the name is wrong, or the hotspot has no internet.\n", host.c_str());
    return;
  }
  Serial.printf("  DNS:  ok -> %s\n", ip.toString().c_str());
  if (ip[0] == 100 && ip[1] >= 64 && ip[1] <= 127) {
    Serial.println("        That is a Tailscale (100.x) address, which only tailnet devices can reach.");
  }

  WiFiClient tcp;
  if (!tcp.connect(ip, port, 8000)) {
    Serial.printf("  TCP:  FAILED to %s:%u. Nothing public is listening on this port: "
                  "Funnel not enabled on %u, or it stopped.\n", ip.toString().c_str(), port, port);
    return;
  }
  tcp.stop();
  Serial.printf("  TCP:  ok on port %u\n", port);

  WiFiClientSecure probe;
  probe.setCACert(HECATE_ROOT_CA);
  if (!probe.connect(host.c_str(), port)) {
    char err[120] = "";
    probe.lastError(err, sizeof(err));
    Serial.printf("  TLS:  FAILED: %s\n", err[0] ? err : "handshake failed");
    return;
  }
  probe.stop();
  Serial.println("  TLS:  ok, certificate verified");

  HTTPClient check;
  String url = String(base) + "/v1/device/settings";
  if (!check.begin(probe, url)) {  // fresh client: the upload connection is left untouched
    Serial.println("  HTTP: could not start request");
    return;
  }
  check.addHeader("Authorization", AUTH_HEADER);
  int code = check.GET();
  check.end();
  switch (code) {
    case 200: Serial.println("  HTTP: 200, backend reachable and token accepted"); break;
    case 401: Serial.println("  HTTP: 401, reached Hecate but the token differs from HECATE_DEVICE_TOKEN"); break;
    case 404: Serial.println("  HTTP: 404, reached the server but not /v1/device; check the funnel --set-path mapping"); break;
    case 503:
      Serial.println("  HTTP: 503, Hecate is running without HECATE_DEVICE_TOKEN set, or the backend is down"); break;
    case 502: case 504:
      Serial.printf("  HTTP: %d, Funnel is up but nothing answers behind it: start uvicorn on port 8000\n", code); break;
    default: Serial.printf("  HTTP: %d %s\n", code, code < 0 ? check.errorToString(code).c_str() : ""); break;
  }
}

// Returns true when the backend answered 2xx.
bool request(const char *path, camera_fb_t *frame) {
  String url = String(BASE_URLS[activeUrl]) + path;
  if (!http.begin(tls, url)) return false;
  http.collectHeaders(HEADER_KEYS, sizeof(HEADER_KEYS) / sizeof(HEADER_KEYS[0]));
  http.addHeader("Authorization", AUTH_HEADER);
  http.addHeader("X-Hecate-Applied", appliedHeader());
  int code;
  if (frame) {
    http.addHeader("Content-Type", "image/jpeg");
    code = http.POST(frame->buf, frame->len);
  } else {
    code = http.GET();
  }
  bool ok = code >= 200 && code < 300;
  if (ok) {
    readSettingsHeaders();
  } else if (code == 401) {
    Serial.println("Backend rejected the device token: check HECATE_DEVICE_TOKEN on both sides");
  } else {
    Serial.printf("Request failed (%s): %d %s\n", BASE_URLS[activeUrl], code,
                  code < 0 ? http.errorToString(code).c_str() : "");
  }
  http.end();  // Keeps the TLS connection open for reuse when the server allows it.
  return ok;
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\nHecate wearable camera");

  if (!startCamera()) {
    delay(5000);
    ESP.restart();
  }

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);  // Power-bank powered; latency matters more than battery here.
  wifi.addAP(WIFI_SSID, WIFI_PASSWORD);
  if (strlen(WIFI_SSID_2) > 0) wifi.addAP(WIFI_SSID_2, WIFI_PASSWORD_2);
  connectWifi();

  tls.setCACert(HECATE_ROOT_CA);
  http.setReuse(true);
  http.setTimeout(8000);
  http.setConnectTimeout(8000);

  for (size_t i = 0; i < BASE_URL_COUNT; i++) {
    if (strlen(BASE_URLS[i]) > 0) diagnose(BASE_URLS[i]);  // a backup set to "" counts as unset
  }
}

// After repeated failures, explain why (at most every 30 s) and try the next URL.
void handleFailure() {
  if (++consecutiveFailures < FAILURES_BEFORE_SWITCH) return;
  consecutiveFailures = 0;
  if (millis() - lastDiagnosisAt > DIAGNOSE_EVERY_MS) diagnose(BASE_URLS[activeUrl]);
  size_t next = activeUrl;
  for (size_t i = 1; i < BASE_URL_COUNT; i++) {
    size_t candidate = (activeUrl + i) % BASE_URL_COUNT;
    if (strlen(BASE_URLS[candidate]) > 0) { next = candidate; break; }
  }
  if (next != activeUrl) {
    activeUrl = next;
    http.end();
    tls.stop();
    Serial.printf("Switching to %s\n", BASE_URLS[activeUrl]);
  }
}

void loop() {
  connectWifi();
  uint32_t started = millis();

  bool ok;
  if (current.paused) {
    ok = request("/v1/device/settings", nullptr);
  } else {
    camera_fb_t *frame = esp_camera_fb_get();
    if (!frame) {
      Serial.println("Frame capture failed");
      delay(200);
      return;
    }
    ok = request("/v1/device/frame", frame);
    esp_camera_fb_return(frame);
    if (ok && ++framesSent % 25 == 0) {
      Serial.printf("%lu frames sent, last cycle %lu ms\n", (unsigned long)framesSent, (unsigned long)(millis() - started));
    }
  }

  if (ok) consecutiveFailures = 0;
  else handleFailure();
  backoffMs = ok ? 0 : min<uint32_t>(MAX_BACKOFF_MS, backoffMs ? backoffMs * 2 : 500);
  uint32_t target = current.paused ? PAUSED_POLL_MS : current.intervalMs;
  uint32_t elapsed = millis() - started;
  uint32_t wait = (elapsed < target ? target - elapsed : 0) + backoffMs;
  if (wait) delay(wait);
}
