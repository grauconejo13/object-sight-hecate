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

## Status

🕷️ **Milestone 1 in progress — single-camera perception**

The current goal is deliberately small: verify reliable single-camera capture, detection/tracking, and basic wearer-relative positioning before adding trajectory reasoning, selective alerts, multi-camera fusion, or AWS orchestration.

See [`docs/project-brief.md`](docs/project-brief.md), [`docs/architecture.md`](docs/architecture.md), and [`docs/BUILD_LOG.md`](docs/BUILD_LOG.md).
