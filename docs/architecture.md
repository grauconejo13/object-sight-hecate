# Architecture Notes

This document captures the intended build order without locking the project into a final implementation.

## Phase 1 — Perception Foundation

```text
Image / Video / Camera
        ↓
      OpenCV
        ↓
      Detector
        ↓
boxes + labels + confidence
```

This is the first thing that must work reliably.

## Phase 2 — Temporal Awareness

```text
frames
  ↓
detection
  ↓
tracking
  ↓
position + direction + relative motion
  ↓
short event history
```

The system begins reasoning over change instead of isolated frames.

## Phase 3 — Spatial Awareness

The wearer becomes the reference point for observations.

Candidate outputs:

- clock position / relative direction
- approaching vs receding
- approximate distance or proximity band
- crossing trajectory
- obstacle location
- persistent presence in a blind area

Depth may initially be approximate. Dedicated depth hardware can be evaluated later.

## Phase 4 — Awareness Engine

```text
observation
   ↓
spatial + temporal state
   ↓
relevance / alert rules
   ├── no alert
   ├── haptic cue
   ├── directional audio
   └── request another observation
```

Important design goal: **silence is a valid output**.

## Phase 5 — Hecate Multi-View Fusion

Future concept:

```text
camera A ----\
camera B -----+--> normalize / synchronize --> shared spatial model
camera C ----/
```

The first implementation does not require custom hardware or three physical cameras. Multi-view fusion should only be attempted after the single-camera pipeline is reliable.

## Phase 6 — Adaptive Vision

Potential later inputs:

- scene brightness
- blur level
- user motion
- object velocity
- low-visibility conditions

Potential responses:

- exposure adjustment when supported
- frame-rate adjustment
- denoising / contrast enhancement
- alternate processing path for low-light scenes

The purpose is not cosmetic enhancement; it is maintaining useful perception when conditions change.

## Phase 7 — AWS / Agentic Layer

```text
local vision pipeline
      ↓
structured event
      ↓
AWS service / agent
      ├── request another observation
      ├── summarize evidence
      ├── ask for human confirmation
      └── trigger a non-safety-critical follow-up
```

Immediate collision or safety alerts should not depend on a slow cloud reasoning round trip. Local deterministic logic should handle time-sensitive alerts where practical.

## Deliberately Deferred

Do not build these until the perception foundation justifies them:

- custom wearable hardware
- three-camera physical rig
- mobile application
- user accounts
- persistent cloud video storage
- facial recognition
- emotion or intent classification
- custom-trained models
- production emergency-response integrations
