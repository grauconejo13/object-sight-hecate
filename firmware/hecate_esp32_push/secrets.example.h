// Copy this file to secrets.h (same folder) and fill it in. secrets.h is gitignored.
#pragma once

// Your phone's hotspot (2.4 GHz). On iPhone turn on "Maximize Compatibility".
#define WIFI_SSID "your-phone-hotspot"
#define WIFI_PASSWORD "hotspot-password"

// Optional second network, e.g. home Wi-Fi for bench testing. Leave "" to skip.
#define WIFI_SSID_2 ""
#define WIFI_PASSWORD_2 ""

// Public Funnel URL of the laptop backend, no trailing slash. Port 8443 is the
// Funnel port that only exposes /v1/device (see docs/ESP32_CAMERA.md).
#define HECATE_BASE_URL "https://your-laptop.your-tailnet.ts.net:8443"

// Optional second backend, tried after 3 failures in a row. Only useful if the
// phone app also reads from it (its VITE_API_URL points at one backend).
// #define HECATE_BACKUP_URL "https://other-laptop.your-tailnet.ts.net:8443"

// Must match HECATE_DEVICE_TOKEN on the backend. Generate one with:
//   python -c "import secrets; print(secrets.token_urlsafe(24))"
#define HECATE_DEVICE_TOKEN "paste-the-same-long-random-token-here"
