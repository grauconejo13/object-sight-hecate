# Build Log

Chronological record of meaningful Object-Sight Hecate build sessions.

Use this file to capture what changed, what worked, what failed, and what should happen next.

## 2026-09-15 — Milestone 1 completed: single-camera perception

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
- Verified clean in-app exits in two consecutive launches using the `Q` / `Esc` controls, with no traceback on return to PowerShell.

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
- Application shutdown controls work cleanly without needing Ctrl+C.

**Problems / failures**

- Initial dependency installation stopped while installing PyTorch with `OSError: [Errno 28] No space left on device`.
- The system drive was cleaned up and the environment proceeded afterward.
- Object classification is sensitive to pose and available COCO classes: a soda/pop can may be labeled `cell phone`, a flat book may be missed while an open book is detected, and a plant/pot can alternate between `cup` and `potted plant`.
- One camera run emitted `WARNING not enough matching points` from tracker motion compensation. This did not prevent later clean launches and exits, but remains a useful tracker failure case to monitor.
- Re-identification after a subject fully leaves the frame is not supported in Milestone 1.
- No trajectory, distance, relevance scoring, selective alerts, or AWS behavior exists yet.

**Evidence / measurements**

- Local Python version: `3.11.5`.
- Runtime OpenCV version observed: `5.0.0`.
- First webcam run resolution: `1280x720`.
- Initial observed performance: approximately `13.3 FPS`; live FPS fluctuates during movement.
- Live detections visibly included confidence scores, track IDs, and wearer-relative clock-position hints.
- Spatial direction mapping passed the first manual movement test.
- Unit tests: `3 passed`, runtime `0.001s`.
- Two final camera launches exited cleanly back to PowerShell without exception using in-app controls.
- Failure cases are recorded in `docs/PERFORMANCE.md` for later evaluation.

**Milestone result**

Milestone 1 is complete and the feature branch is ready for merge into `main`.

**Next step**

- Merge Milestone 1 when ready.
- Begin Milestone 2 with short per-track position history.
- Add movement-direction estimation before attempting approaching / receding classification.

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
