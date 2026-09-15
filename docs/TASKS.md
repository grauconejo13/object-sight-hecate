# Tasks

Working checklist for Object-Sight Hecate development.

Use this file to track milestone progress, validation work, and the next concrete build step. Check items only after they are implemented **and** verified where verification is required.

## Milestone 1 — Single-Camera Perception

### Repository / setup

- [x] Create private `object-sight-hecate` repository.
- [x] Add project architecture and documentation scaffolding.
- [x] Create `feature/single-camera-perception` branch.
- [x] Open draft PR for Milestone 1.
- [x] Pin OpenCV 5 dependency.
- [x] Pin Ultralytics / YOLO dependency.

### Camera + perception

- [x] Open webcam or video source with OpenCV.
- [x] Read frames continuously.
- [x] Run object detection.
- [x] Add persistent tracking IDs.
- [x] Draw bounding boxes.
- [x] Display class label and confidence.
- [x] Display track ID.
- [x] Display OpenCV version.
- [x] Display live FPS.

### Basic spatial awareness

- [x] Calculate object center position.
- [x] Divide the image into left / ahead / right regions.
- [x] Map horizontal position to initial clock hints:
  - [x] `9 o'clock` — left
  - [x] `12 o'clock` — ahead
  - [x] `3 o'clock` — right
- [x] Add unit tests for spatial mapping.

### Local validation required

- [x] Pull / switch to `feature/single-camera-perception` locally.
- [x] Create and activate the Python virtual environment.
- [x] Install dependencies successfully.
- [x] Verify runtime is using OpenCV 5.x. **Observed: OpenCV 5.0.0.**
- [ ] Run unit tests locally.
- [x] Open the webcam successfully.
- [x] Confirm the YOLO model loads successfully.
- [ ] Test movement from left -> center -> right.
- [ ] Test another person or object crossing the frame.
- [ ] Check track-ID stability across movement.
- [x] Record baseline FPS. **Initial observed run: ~13.3 FPS at 1280x720.**
- [ ] Record obvious detection / tracking failure cases.
- [ ] Verify `Q` and `Esc` stop the application cleanly.

### Milestone 1 exit criteria

- [ ] Camera loop runs reliably on the project laptop.
- [ ] Detection is reliable enough for prototype use.
- [ ] Tracking IDs are usable for temporal reasoning.
- [ ] Left / ahead / right spatial mapping behaves correctly.
- [ ] Baseline real-time performance is documented.
- [ ] Major failure cases are documented.
- [ ] Draft PR is ready to merge into `main`.

---

## Milestone 2 — Temporal Spatial Awareness

Planned after Milestone 1 passes local validation.

- [ ] Maintain short position history per track ID.
- [ ] Estimate object movement direction.
- [ ] Distinguish approaching vs receding motion where evidence supports it.
- [ ] Detect meaningful crossing trajectories.
- [ ] Convert temporal state into structured spatial events.
- [ ] Add unit tests for trajectory calculations.
- [ ] Add scenario tests for moving subjects.
- [ ] Record latency and failure cases.

Target progression:

```text
track ID
   ↓
position history
   ↓
movement direction
   ↓
approaching / receding
   ↓
trajectory
   ↓
spatial event
```

---

## Later Milestones — Not Started

These are intentionally deferred so Milestone 1 stays small and testable.

- [ ] Selective alert / relevance engine.
- [ ] Directional audio and/or haptic cues.
- [ ] Multi-camera Hecate architecture.
- [ ] Low-light / adaptive capture experiments.
- [ ] AWS event pipeline.
- [ ] Agentic Vision perception -> decision -> action loop.
- [ ] Human-confirmation workflow where appropriate.
- [ ] Evaluation dataset / repeatable scenario suite.
- [ ] Final architecture diagram.
- [ ] Final technical report.
- [ ] Judge demo / video preparation.

## Current next action

Run the unit tests, then exercise the live camera with left -> center -> right movement and a crossing subject/object. Record track-ID stability and obvious failures before declaring Milestone 1 complete.
