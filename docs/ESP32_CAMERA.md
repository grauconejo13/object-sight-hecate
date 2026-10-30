# Wearable ESP32 camera

The ESP32-S3-EYE is worn facing **behind** you, powered from a power bank over USB-C, and joined to **your phone's hotspot**. It runs no AI. It pushes JPEG frames to the Hecate backend on the laptop, which runs detection, tracking and alert rules. The phone app shows the feed and speaks alerts.

```text
ESP32 cam ──HTTPS POST frame + token──▶ Tailscale Funnel :8443 (/v1/device only)
   (phone hotspot, cell data)                     │
                                                  ▼
                                   FastAPI on the laptop (YOLO + tracking + alerts)
                                                  ▲
Phone app ──tailnet only (:443)── GET /v1/esp32/latest, frame.jpg, PUT settings
```

Why push: on the hotspot nothing can connect *to* the ESP32, it cannot run Tailscale, and an HTTPS page cannot load a plain-HTTP camera. Pushing avoids all three. Settings changed in the app travel back to the camera in the response headers of its next upload, so the camera never needs an open port.

## 1. Backend (laptop, PowerShell)

Generate a device token once and keep it out of the repository:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

Start the API with it:

```powershell
.\.venv\Scripts\Activate.ps1
$env:HECATE_DEVICE_TOKEN = "paste-the-token"
$env:FRONTEND_ORIGINS = "https://your-hecate-site.vercel.app"
uvicorn object_sight_hecate.web_api:app --host 127.0.0.1 --port 8000
```

Without `HECATE_DEVICE_TOKEN` (16+ characters) the device endpoints refuse every upload.

## 2. Tailscale: keep the app private, expose only the upload path

Your existing `tailscale serve` on port 443 stays tailnet-only; that is what `VITE_API_URL` on Vercel points at. Add a **separate** Funnel on port 8443 that mounts only `/v1/device`:

```powershell
tailscale funnel --bg --https=8443 --set-path=/v1/device http://127.0.0.1:8000/v1/device
tailscale funnel status
```

The first time, Tailscale may print a link to enable Funnel for your tailnet; open it, approve, and rerun.

**Check the exposure before going outside.** On the phone, turn the Tailscale VPN **off** and Wi-Fi **off** (cell data only), then open:

| URL | Expected |
| --- | --- |
| `https://<laptop>.<tailnet>.ts.net:8443/v1/device/settings` | `401 Invalid device token` (reachable, protected) |
| `https://<laptop>.<tailnet>.ts.net:8443/health` | 404 (nothing else mounted) |
| `https://<laptop>.<tailnet>.ts.net/v1/esp32/latest` | does not load (tailnet-only) |

If `/v1/device/settings` returns 404 instead of 401, your Tailscale version forwards the full path: run `tailscale funnel --https=8443 --set-path=/v1/device off`, then repeat the funnel command with the target `http://127.0.0.1:8000` and check again.

If `/health` or `/v1/esp32/latest` loads publicly, run `tailscale funnel reset`, check `tailscale funnel status`, and redo the command above. Do not put the whole port 443 on Funnel: that would make the camera feed and `/v1/analyze` public.

Turn Tailscale back on for the phone afterwards; the app needs it.

## 3. Flash the camera

1. Arduino IDE with the **esp32 by Espressif** boards package.
2. Open `firmware/hecate_esp32_push/hecate_esp32_push.ino`.
3. Copy `secrets.example.h` to `secrets.h` in the same folder and fill in the hotspot name and password, `HECATE_BASE_URL` (`https://<laptop>.<tailnet>.ts.net:8443`, no trailing slash) and the same token. `secrets.h` is gitignored.
4. Tools: Board **ESP32S3 Dev Module**, PSRAM **OPI PSRAM**, a partition scheme with at least 3 MB app, USB CDC On Boot **Enabled** (to see logs over USB-C).
5. Upload, open Serial Monitor at 115200. Expected: `Connected to <hotspot>`, then `25 frames sent, …` every so often.

`root_ca.h` holds the public Let's Encrypt roots, so the camera verifies it is talking to your Funnel URL before sending the token.

The pin map is the same `CAMERA_MODEL_ESP32S3_EYE` one your CameraWebServer test used. The sketch has not been compiled in CI; if the IDE reports an API mismatch, note the core version (Tools > Board > Boards Manager) and the error.

## 4. Hotspot

- The ESP32 only joins **2.4 GHz**. iPhone: Settings > Personal Hotspot > turn on **Maximize Compatibility**. Android: set the hotspot band to 2.4 GHz.
- Keep the phone's hotspot screen or settings open the first time so the ESP32 joins.
- Optional: put home Wi-Fi in `WIFI_SSID_2` for bench testing; the camera uses whichever network it finds.

## 5. Phone app

1. Open the Vercel URL with Tailscale on.
2. Tap **ESP32 cam** in the top-right toggle, then **Watch** (▶). Speech turns on and the screen is kept awake while watching.
3. The gear opens **camera settings**: which way the camera faces, resolution, frame rate, image quality, flip, mirror, and pause. **Save to camera** applies on the next frame (within about 3 s while paused).

Badge states: `ESP32 CAM · REAR · LIVE` when frames arrive, `WAITING` when the camera has gone quiet for more than 6 s.

## 6. Orientation check (do this once with the camera worn)

Positions for a rear-facing camera: image left = **5 o'clock** (behind your right), centre = **6**, image right = **7** (behind your left).

1. Wear the camera, face away from a helper.
2. Helper stands behind your **right** shoulder: the app should say 5 o'clock.
3. If it says 7, toggle **Mirror image left/right** in settings and test again. If the image is upside down, toggle **Flip**.

Record the result in `docs/BUILD_LOG.md`.

## Alerts

Local rules on the laptop decide what is spoken; no network AI round trip is involved:

- **New person behind you**, once per track, after it has been seen in 3 frames.
- **Getting larger in view** (warning): the box of a person, bicycle, motorbike, car, bus, truck or dog grew by 10 %+ across recent frames. This is a monocular size cue, not a distance measurement. Warnings can interrupt; notices wait for a 4 s gap.
- **Crossing behind you**: a full left-third to right-third traversal.

Objects below 50 % confidence and other classes stay on screen only.

## Privacy

Only the newest frame is held in memory on the laptop; nothing is written to disk. The evidence export records model outputs and timing, never images. Do not commit Wi-Fi credentials, the token, or captured footage.

## Troubleshooting

### Works on Wi-Fi, fails on the phone's hotspot over cellular

Seen on T-Mobile: the camera joined the hotspot and DNS worked, but `Internet: FAILED` (no IPv4 route), while other phones on the same hotspot were fine. T-Mobile's network is IPv6-only, so the likely cause is that the camera's IPv4 traffic isn't passed. The firmware turns on IPv6 (`WiFi.enableIPv6()`) and the diagnostics print `IPv6: address …` and `Internet over IPv6: …`, which show whether the IPv6 path works on your hotspot. **Confirmed in the field (Oct 30, 2026):** with IPv6 enabled, the camera streamed live over a T-Mobile 5G hotspot (about 3.6 MB of hotspot data in under 2 minutes, roughly one 640×480 frame per second). It can take up to a minute to join the hotspot after power-on. This needs the esp32 board package 3.x.

### "Request failed: -1 connection refused"

`-1` is HTTPClient's catch-all for "could not connect". DNS failure, nothing listening on the port, and a failed TLS handshake all report the same code. The firmware therefore checks each stage at boot, and again after repeated failures, and prints which one fails:

| Serial line | Meaning | Fix on the laptop running Hecate |
| --- | --- | --- |
| `DNS: FAILED` | The name isn't publicly resolvable. Without Funnel, a `*.ts.net` name resolves only for tailnet devices, and the ESP32 is not one (hotspot clients don't use the phone's Tailscale). | `tailscale funnel status`: the 8443 entry must say **Funnel on**. If not, rerun the funnel command in step 2. |
| `DNS: ok -> 100.x.x.x` | Resolved to a private Tailscale address; only tailnet devices can reach it. | Same: Funnel must be on. |
| `TCP: FAILED` | Nothing public is listening on that port. | Funnel off for 8443, the laptop asleep or offline, or Tailscale stopped. |
| `TLS: FAILED: …` | Reached a server, but the certificate didn't verify. | Note the error text. A date or "expired" message points at the ESP32's clock. |
| `HTTP: 404` | Funnel is up but `/v1/device` isn't mapped. | Check the `--set-path` mapping (see step 2). |
| `HTTP: 502` / `504` | Funnel is up, but nothing answers behind it. | Start uvicorn on port 8000. |
| `HTTP: 503` | Hecate is running without the device token, or is down. | Set `HECATE_DEVICE_TOKEN` and restart uvicorn. |
| `HTTP: 401` | Everything works except the token. | Make the token in `secrets.h` match `HECATE_DEVICE_TOKEN`. |
| `HTTP: 200` | Reachable and authorised. | — |

Check from outside your tailnet, just as the ESP32 is: on the phone, turn **Tailscale off** and Wi-Fi off (cell data only), then open `https://<laptop>.<tailnet>.ts.net:8443/v1/device/settings`. Expect `401` (or `{"detail":"Invalid device token"}`). If it doesn't load, the problem is on the laptop side, not the ESP32.

`HECATE_BACKUP_URL` (optional, in `secrets.h`) is tried after 3 failures in a row. It must point at a laptop that runs Hecate with Funnel on 8443, and the phone app only shows frames from the backend in its `VITE_API_URL`.


- **`Request failed: -1`** on Serial: TLS or DNS failure. Check `HECATE_BASE_URL` (https, `:8443`, no trailing slash) and that Funnel is on.
- **`rejected the device token`**: the token differs between `secrets.h` and `HECATE_DEVICE_TOKEN`.
- **App says waiting but Serial shows frames sent**: the phone is not on Tailscale or `VITE_API_URL` points elsewhere.
- **Settings don't seem to change**: after Save, the settings sheet says "Camera applied the new settings ✓" once the camera reports back. "Isn't reporting its settings" means the camera runs firmware older than this fix: reflash. "Hasn't applied: …" names the setting; the Serial Monitor prints `Settings applied: …` on every change, or `Response had no X-Hecate-* settings headers` if the Funnel path is wrong.
- **Laggy**: lower resolution to QVGA or frame rate to ~1.5 fps; raise image quality number (smaller uploads).
- **Camera init failed**: PSRAM setting is wrong or the ribbon cable is loose.

## Bench test without the hotspot (older path)

The desktop detector can still pull from Espressif's CameraWebServer on the same Wi-Fi:

```powershell
python main.py --source "http://192.168.1.25:81/stream"
python main.py --source "http://192.168.1.25/capture"
```
