# Object-Sight Hecate

**Object-Sight Hecate** is an experimental computer-vision project exploring **artificial peripheral awareness**: an extra set of eyes for people moving through environments where attention, visibility, or familiarity may be limited.

This repository is the private competition build for the **OpenCV AI Competition 2026, powered by AWS**.

## Core Idea

Object-Sight should not simply announce everything a camera detects. The goal is to maintain a lightweight spatial understanding of the environment around the user and surface only meaningful changes.

Example future alerts:

- `Cyclist approaching, 5 o'clock.`
- `Movement closing from rear-left.`
- `Obstacle ahead.`

The system focuses on observable position, motion, trajectory, and spatial relationships rather than trying to infer a person's identity, intentions, trustworthiness, or emotions.

## Candidate Scenarios

- Walking at night in a city
- Traveling alone in an unfamiliar area
- Jogging or running
- Hiking and trail navigation
- Low-visibility environments
- Accessibility assistance

The hackathon prototype will demonstrate a small subset well rather than claim to solve every scenario.

## Hecate

**Hecate** is the working name for the project's multi-view perception architecture, inspired by the goddess associated with crossroads, night, thresholds, and later triple-form imagery.

A future physical implementation may use three wide-angle cameras to provide complementary views around the wearer. Custom hardware is **not required** for the initial prototype.

## Planned Progression

```text
camera input
    ↓
OpenCV perception
    ↓
object detection / tracking
    ↓
spatial relationships + trajectories
    ↓
relevance / awareness engine
    ↓
quiet | haptic cue | directional audio | follow-up action
```

Later stages may add multi-camera fusion, adaptive low-light capture, pose/activity cues, depth estimation, and an AWS-backed agentic layer.

## Design Principles

- Awareness sessions are deliberately started and stopped by the user.
- Silence is a valid output; do not narrate everything.
- Prefer local processing for routine perception where practical.
- Avoid continuous video storage by default.
- Do not require facial recognition.
- Do not infer criminal intent, personality, trustworthiness, or emotion from appearance.
- Describe observable spatial behavior instead.
- Time-critical safety alerts should not depend on a remote AI round trip.
- Human judgment remains responsible for consequential decisions.

## Initial Stack

- Python
- OpenCV 5
- Ultralytics YOLO for the first detector/tracker adapter
- NVIDIA Nemotron on Nebius Token Factory for optional scene briefings
- AWS services where they add meaningful agentic or cloud capability

Dependencies are pinned as the competition build stabilizes.

## First Prototype

The first vertical slice now supports:

- OpenCV 5 camera or video input
- object detection and persistent track IDs
- wearer-relative left / ahead / right positioning
- initial clock-direction hints (`9`, `12`, `3`)
- on-screen detection, confidence, track ID, OpenCV version, and FPS overlays

### Run locally

```bash
python -m venv .venv
```

Activate the environment, then:

```bash
pip install -r requirements.txt
python main.py --source 0
```

Press `q` or `Esc` to stop. A video path can be supplied instead of camera index `0`.

Run the current unit tests with:

```bash
python -m unittest discover -s tests
```

The first model may download automatically on initial use.

## ESP32 and phone field tests

- **Wearable ESP32 cam:** an ESP32-S3-EYE worn facing behind you, on a power bank and your phone's hotspot, pushes frames to the backend. The phone app switches between **Phone** and **ESP32 cam**, shows the feed with rear-relative clock positions (5 / 6 / 7 o'clock), speaks alerts, and edits the camera's settings remotely. See [ESP32 camera setup](docs/ESP32_CAMERA.md).
- The desktop detector can still read the ESP32 CameraWebServer stream on the same Wi-Fi for bench tests.
- A separate phone-camera preview is ready for Vercel (frontend) and Render (analysis API). It sends one image only when you tap Analyze. See [field test deployment](docs/FIELD_TEST_DEPLOY.md).

These are input and testing paths for the same perception core. Remote cloud inference is experimental and is not used for time-critical alerts. The final OpenCV AI Competition entry still needs a meaningful AWS component.

## Scene briefing: NVIDIA Nemotron on Nebius Token Factory

Tap **Ask Hecate** (✦) and Hecate speaks one cautious sentence about what it is tracking, e.g. *"Rear view: a person at 6 o'clock and a car at 7 o'clock."*

- **How Nemotron is used:** the backend sends Nemotron (`nvidia/nemotron-3-super-120b-a12b` by default) the structured scene from YOLO and tracking (labels, clock directions, view-size trends, and the last 30 s of local alerts) through Token Factory's OpenAI-compatible API. Nemotron prioritises and groups it into one sentence that can be taken in by ear. No images or boxes leave the laptop.
- **Why it matters:** detections are per-box and per-frame; a person walking needs one prioritised summary of the scene. That aggregation is the model's job here.
- **What stays local:** detection, tracking and the time-critical spoken alerts never wait on the cloud.
- **Guardrails:** every reply is checked locally. Claims of identity, intent, danger or distance, or directions not in the data, are discarded for a deterministic local summary. The app shows which one you are hearing, and when Nebius is unavailable.
- **Setup:** set `NEBIUS_API_KEY` on the backend. Details in [docs/NEBIUS.md](docs/NEBIUS.md).

## Status

🕷️ **Milestone 1 in progress — single-camera perception**

The current goal is deliberately small: verify reliable single-camera capture, detection/tracking, and basic wearer-relative positioning before adding trajectory reasoning, selective alerts, multi-camera fusion, or AWS orchestration.

See [`docs/project-brief.md`](docs/project-brief.md), [`docs/architecture.md`](docs/architecture.md), and [`docs/BUILD_LOG.md`](docs/BUILD_LOG.md).
