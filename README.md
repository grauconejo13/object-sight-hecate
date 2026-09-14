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
- Pretrained object detection / tracking tooling
- AWS services where they add meaningful agentic or cloud capability

Additional libraries will be added only when a concrete feature requires them.

## Status

🕷️ **Pre-build / architecture stage**

The first technical milestone will remain deliberately small: prove reliable perception from a single camera before adding spatial reasoning or multi-camera fusion.

See [`docs/project-brief.md`](docs/project-brief.md) and [`docs/architecture.md`](docs/architecture.md).
