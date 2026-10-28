# Object-Sight Hecate

**Object-Sight Hecate** explores **artificial peripheral awareness**: an extra set of eyes for people walking, running, or travelling alone where attention or visibility is limited. A small camera worn facing behind you watches the space you can't, and your phone tells you, briefly and calmly, what is there.

Built for the **Nebius Global AI Hackathon with NVIDIA** (Physical AI track). It runs **NVIDIA Nemotron on Nebius Token Factory** to turn what the camera is tracking into one spoken sentence.

## What it does

- **Wearable rear camera.** An ESP32-S3-EYE with a wide lens, powered from a pocket power bank and joined to your phone's hotspot, pushes frames to the Hecate backend.
- **Local perception.** OpenCV 5 and Ultralytics YOLO detect and track objects; each one gets a direction around the wearer as a clock position (behind you is 6 o'clock).
- **Local alerts, never waiting on the cloud.** Conservative rules speak only meaningful changes: a person appearing behind you, something growing larger in view, something crossing behind you.
- **Ask Hecate (✦): a scene briefing by NVIDIA Nemotron.** On request, Nemotron on Nebius Token Factory summarises the tracked scene as one cautious sentence, for example *"Rear view: a person at 6 o'clock and a car at 7 o'clock."*
- **Phone app.** Switch between the phone camera and the ESP32 cam, see detections, hear alerts and briefings, and change the camera's settings remotely.

The system describes observable position and change. It never infers identity, intent, emotion, or danger, and it does not claim distances it cannot measure.

## How NVIDIA Nemotron and Nebius Token Factory are used

The hackathon requires every project to run on Nebius Token Factory or Nebius AI Cloud and to use at least one NVIDIA open model. Hecate meets this with **`nvidia/nemotron-3-super-120b-a12b` served by Nebius Token Factory** through its OpenAI-compatible API (`https://api.tokenfactory.nebius.com/v1`). **A Nebius API key (`NEBIUS_API_KEY`) is required to run Hecate as submitted.** Without one, the app keeps working, but every briefing is labelled "Nebius unavailable · local summary" so it is always clear which you are hearing.

**Why a language model here.** YOLO answers "what is in this frame and where is each box" in milliseconds. A person walking with the phone in a pocket needs something else: one prioritised sentence covering the whole scene and what just changed. Nemotron does that aggregation. It groups repeats ("two people at 6 o'clock"), orders people before vehicles before objects, and folds in the last 30 seconds of local alerts.

**What Nemotron receives.** Structured facts only: object labels, clock directions, whether each looks larger or smaller in view, and recent alerts. No images, bounding boxes, or track IDs leave the laptop.

**How its output is kept honest.** A local guard checks every reply against those facts and discards it if it:

- names an object that is not in the facts (a "person" or "car" that YOLO did not report)
- places an object at a direction, or claims a count, the facts do not support
- claims identity, intent, danger, or distance

A discarded reply is replaced by a deterministic local summary, and the app says so. Configuration, API, and the full guard: [docs/NEBIUS.md](docs/NEBIUS.md).

## Architecture

```text
ESP32-S3-EYE (worn facing back) ──HTTPS + device token──┐
Phone camera (browser) ──────────── JPEG ───────────────┤
                                                        ▼
                              FastAPI backend on the laptop
             OpenCV 5 + YOLO ─▶ tracking ─▶ clock direction ─▶ local alert rules ──▶ spoken alerts (fast path)
                                    │
                                    └─ structured facts ─▶ NVIDIA Nemotron on Nebius Token Factory
                                                              │
                                                     local guard ─▶ Ask Hecate briefing (on request)
                                                        ▲
                     Phone web app (Vite, on Vercel) ───┘ over Tailscale
```

## Setup

Requirements: Python 3.11+, Node 20+, a [Nebius Token Factory](https://tokenfactory.nebius.com/) API key. The ESP32 camera and Tailscale are needed only for the wearable mode.

**1. Backend (laptop)**

```bash
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1   macOS/Linux: source .venv/bin/activate
pip install -r requirements-web.txt
```

Set keys in the shell that starts the server (never in source or `web/.env*`):

```powershell
$env:NEBIUS_API_KEY = "your-token-factory-key"       # required for Nemotron briefings
$env:HECATE_DEVICE_TOKEN = "long-random-token"        # only for the ESP32 cam
$env:FRONTEND_ORIGINS = "https://your-app.vercel.app" # only when the app is hosted
uvicorn object_sight_hecate.web_api:app --host 127.0.0.1 --port 8000
```

Check Nemotron is configured: `curl http://127.0.0.1:8000/v1/briefing/status` should show `"available": true`.

**2. Phone web app**

```bash
cd web
cp .env.example .env.local   # sets VITE_API_URL, the backend URL only
npm install
npm run dev
```

Deploying the app to Vercel and reaching the backend from a phone: [docs/FIELD_TEST_DEPLOY.md](docs/FIELD_TEST_DEPLOY.md).

**3. Wearable ESP32 camera (optional)**

Firmware, hotspot setup, and the Tailscale Funnel configuration that exposes only the upload path: [docs/ESP32_CAMERA.md](docs/ESP32_CAMERA.md).

**4. Desktop viewer (optional)**

```bash
pip install -r requirements.txt
python main.py --source 0      # webcam; or a video path, or an ESP32 stream URL
```

**Tests**

```bash
python -m unittest discover -s tests
cd web && node --test tests/*.test.js
```

The Token Factory client is mocked in tests; no test calls the real API.

## Built during the hackathon

Hecate was created entirely within the submission period (Aug 26 – Oct 30, 2026); the first commit is from Sep 14, 2026. The work, in order:

- **Single-camera perception (Sep):** OpenCV 5 + Ultralytics YOLO detection and tracking, wearer-relative clock directions, unit tests.
- **Temporal awareness (Sep):** per-track motion, view-size trend, crossing detection, and a structured spatial-event format.
- **Phone field-test app (Sep–Oct):** live analysis from the phone camera, spoken detections, Have my back with person focus, evidence export.
- **Wearable ESP32 camera (Oct):** push firmware over the phone's hotspot, token-protected ingest, server-side tracking, rear-facing directions, local alert rules, remote camera settings confirmed by the device.
- **NVIDIA Nemotron scene briefing on Nebius Token Factory (Oct):** structured facts only, a local guard against invented objects, directions, counts, identity, intent, danger, and distance, and visible provenance in the app.
- **Product experience (Oct):** the field-instrument interface, first-run intro, sound check, and vibration on warnings.

## Design principles

- Awareness sessions are started and stopped by the user.
- Silence is a valid output; do not narrate everything.
- Time-critical alerts run locally and never wait on a cloud round trip.
- No continuous video storage: only the newest frame is held in memory.
- No facial recognition; no inference of identity, intent, trustworthiness, or emotion.
- Describe observable position and change; do not claim distance from a single camera.
- Human judgment remains responsible for consequential decisions.

## Limitations

- "Larger in view" is a bounding-box size cue from one camera. Camera movement, pose, and occlusion affect it; it is not a distance measurement.
- Detection quality drops in low light and with motion blur from walking.
- The backend runs on a laptop reached over Tailscale; latency depends on the phone's mobile connection.
- Track IDs reset when an object leaves the frame.

## Roadmap

- **Hecate:** three wide-angle cameras for full surround awareness, the origin of the name (the goddess of crossroads and thresholds, often shown in triple form).
- Directional audio and haptic cues.
- Low-light capture and depth or ego-motion cues to replace the size heuristic.
- A repeatable scenario suite to measure alert precision.

More detail: [docs/project-brief.md](docs/project-brief.md), [docs/architecture.md](docs/architecture.md), [docs/BUILD_LOG.md](docs/BUILD_LOG.md).

## License

Hecate's own code is released under the [MIT License](LICENSE). Dependencies keep their own licenses; notably, Ultralytics YOLO is licensed under AGPL-3.0, and using or distributing Hecate together with it is subject to that license.
