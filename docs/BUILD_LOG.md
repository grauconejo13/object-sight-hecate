# Build Log

Chronological record of meaningful Object-Sight Hecate build sessions.

Use this file to capture what changed, what worked, what failed, and what should happen next.

## 2026-09-15 — Milestone 1 started: single-camera perception

**Goal**

- Move from architecture-only scaffolding into the first runnable perception slice.
- Keep scope limited to one camera before trajectory reasoning, multi-view fusion, alerts, or AWS orchestration.

**Built / changed**

- Pinned `opencv-python==5.0.0.93` and `ultralytics==8.4.150`.
- Added an OpenCV-backed camera/video source.
- Added a detector/tracker adapter that returns model-agnostic detection records.
- Added wearer-relative horizontal positioning with initial `9 / 12 / 3 o'clock` hints.
- Added a runnable window with bounding boxes, track IDs, confidence, OpenCV version, and FPS.
- Added initial unit tests for spatial position mapping.
- Added local run instructions to the README.
- Pulled and switched the project laptop to `feature/single-camera-perception`.
- Created and activated a Python 3.11 virtual environment.
- Freed system-drive space after the first PyTorch installation failed, then completed the dependency setup.
- Ran the first live webcam session successfully.
- Completed live left -> center -> right spatial validation.
- Exercised a subject crossing the frame and observed tracker behavior across disappear/re-enter cycles.
- Recorded initial class/pose failure cases.
- Ran the local spatial mapping test suite successfully: 3/3 tests passed in 0.001s.

**What worked**

- Repository now has a complete code path from frame source -> detection/tracking -> spatial observation -> visual overlay.
- OpenCV 5 is explicitly required at runtime so an accidental OpenCV 4 environment fails clearly.
- Local repository sync and branch setup completed successfully.
- Python 3.11.5 virtual environment activated successfully.
- `pip` upgraded successfully before dependency installation.
- OpenCV 5.0.0 launched successfully with the webcam at 1280x720.
- YOLO loaded and produced live detections with track IDs.
- Center, left, and right movement correctly mapped to `12`, `9`, and `3 o'clock` respectively.
- Track IDs can change after a subject fully leaves the camera view and returns; this is acceptable for the current short-term tracking baseline.
- All three current spatial mapping unit tests passed locally.

**Problems / failures**

- Initial dependency installation stopped while installing PyTorch with `OSError: [Errno 28] No space left on device`.
- The system drive was cleaned up and the environment proceeded afterward.
- Object classification is sensitive to pose and available COCO classes: a soda/pop can may be labeled `cell phone`, a flat book may be missed while an open book is detected, and a plant/pot can alternate between `cup` and `potted plant`.
- One later camera run emitted `WARNING not enough matching points` from the tracker and was stopped with Ctrl+C, producing a `KeyboardInterrupt` while OpenCV was waiting on the next capture read.
- `Q` and `Esc` clean-exit behavior still need explicit confirmation.
- No trajectory, distance, relevance scoring, selective alerts, or AWS behavior exists yet.

**Evidence / measurements**

- Local Python version: `3.11.5`.
- Runtime OpenCV version observed: `5.0.0`.
- First webcam run resolution: `1280x720`.
- Initial observed performance: approximately `13.3 FPS`; live FPS fluctuates during movement.
- Live detections visibly included confidence scores, track IDs, and wearer-relative clock-position hints.
- Spatial direction mapping passed the first manual movement test.
- Unit tests: `3 passed`, runtime `0.001s`.
- Failure cases are recorded in `docs/PERFORMANCE.md` for later evaluation.

**Next step**

- Relaunch the live camera and explicitly verify both `Q` and `Esc` stop the application cleanly.
- If both pass, close Milestone 1 and prepare the draft PR for merge before starting temporal spatial awareness.

## 2026-09-14 — Repository initialized

- Created private hackathon repository.
- Added README, project brief, architecture notes, Python package shell, requirements, and ignore rules.
- Defined the working concept as artificial peripheral awareness.
- Reserved Hecate as the working name for the future multi-view perception architecture.
- No feature implementation started.

## Entry Template

### YYYY-MM-DD — Session title

**Goal**

- 

**Built / changed**

- 

**What worked**

- 

**Problems / failures**

- 

**Evidence / measurements**

- 

**Next step**

- 
