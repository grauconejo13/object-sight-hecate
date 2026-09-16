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
- [x] Run unit tests locally. **3/3 spatial mapping tests passed in 0.001s.**
- [x] Open the webcam successfully.
- [x] Confirm the YOLO model loads successfully.
- [x] Test movement from left -> center -> right. **Observed correct 9 / 12 / 3 o'clock transitions.**
- [x] Test a subject crossing the frame. **Self-crossing completed.**
- [x] Check track-ID behavior across movement. **IDs change after leaving the frame and re-entering; no continuous-visible churn was reported.**
- [x] Record baseline FPS. **Initial observed run: ~13.3 FPS at 1280x720; live FPS fluctuates during movement.**
- [x] Record obvious detection / tracking failure cases.
- [x] Verify `Q` and `Esc` stop the application cleanly. **Two consecutive launches returned directly to PowerShell without traceback.**

### Milestone 1 exit criteria

- [x] Camera loop runs reliably on the project laptop.
- [x] Detection is reliable enough for prototype use, with known class/pose limitations documented.
- [x] Tracking IDs are usable for short temporal reasoning while a subject remains continuously visible; re-identification after disappearance is not yet supported.
- [x] Left / ahead / right spatial mapping behaves correctly.
- [x] Baseline real-time performance is documented.
- [x] Major failure cases are documented.
- [x] Milestone 1 PR merged into `main`.

**Milestone 1 status: Complete and merged.**

---

## Milestone 2 — Temporal Spatial Awareness

### First implementation slice

- [x] Create `feature/temporal-spatial-awareness` branch.
- [x] Maintain a bounded short history per track ID.
- [x] Estimate horizontal motion from normalized x-position history.
- [x] Add `moving left`, `moving right`, `steady`, and `unknown` states.
- [x] Add an initial monocular approaching / receding heuristic from bounding-box area change.
- [x] Keep stale track history bounded with an age limit.
- [x] Display temporal motion state in the live overlay.
- [x] Add unit tests for temporal history, horizontal movement, range trend, and isolated track histories.

### Important limitation

The current `approaching` / `receding` state is **not a true distance measurement**. It uses bounding-box area growth/shrinkage as an early monocular heuristic. Camera/wearer motion, pose changes, partial occlusion, and detector-box jitter can all affect it. This must be validated and later combined with ego-motion or stronger depth evidence before it drives consequential alerts.

### Local validation required

- [ ] Pull / switch to `feature/temporal-spatial-awareness` locally.
- [ ] Run the complete unit-test suite.
- [ ] Confirm existing Milestone 1 behavior still works.
- [ ] Move continuously left -> right and confirm temporal direction follows motion.
- [ ] Move continuously right -> left and confirm temporal direction follows motion.
- [ ] Stand mostly still and confirm motion settles to `steady` rather than churning.
- [ ] Approach the stationary camera and observe `approaching` behavior.
- [ ] Move away from the stationary camera and observe `receding` behavior.
- [ ] Record false motion / false range-trend transitions.
- [ ] Record Milestone 2 FPS impact against the ~13.3 FPS Milestone 1 baseline.

### Remaining Milestone 2 work

- [ ] Improve temporal smoothing based on live validation.
- [ ] Detect meaningful crossing trajectories.
- [ ] Convert temporal state into structured spatial events.
- [ ] Add scenario tests for moving subjects.
- [ ] Record latency and failure cases.

Target progression:

```text
track ID
   ↓
short history
   ↓
horizontal motion
   ↓
initial range trend
   ↓
trajectory
   ↓
spatial event
```

---

## Later Milestones — Not Started

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

Switch the project laptop to `feature/temporal-spatial-awareness`, pull the new code, run the full unit-test suite, then perform the first live motion-direction test before tuning thresholds or adding crossing-trajectory logic.
