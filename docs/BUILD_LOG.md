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

**What worked**

- Repository now has a complete code path from frame source -> detection/tracking -> spatial observation -> visual overlay.
- OpenCV 5 is explicitly required at runtime so an accidental OpenCV 4 environment fails clearly.
- Local repository sync and branch setup completed successfully.
- Python 3.11.5 virtual environment activated successfully.
- `pip` upgraded successfully before dependency installation.
- OpenCV 5.0.0 launched successfully with the webcam at 1280x720.
- YOLO loaded and produced live detections with track IDs.
- The first observed frame correctly labeled a person as `ahead (12 o'clock)` and a cell phone on the right as `right (3 o'clock)`.

**Problems / failures**

- Initial dependency installation stopped while installing PyTorch with `OSError: [Errno 28] No space left on device`.
- The system drive was cleaned up and the environment was able to proceed afterward.
- Unit tests have not yet been confirmed locally.
- Left -> center -> right movement, crossing behavior, track-ID stability, and clean keyboard exit still need explicit validation.
- No trajectory, distance, relevance scoring, selective alerts, or AWS behavior exists yet.

**Evidence / measurements**

- Local Python version: `3.11.5`.
- Runtime OpenCV version observed: `5.0.0`.
- First webcam run resolution: `1280x720`.
- Initial observed performance: approximately `13.3 FPS`.
- Live detections visibly included confidence scores, track IDs, and wearer-relative clock-position hints.

**Next step**

- Run `python -m unittest discover -s tests -v` and record the result.
- Exercise the live camera with left -> center -> right movement.
- Test another person or object crossing the frame.
- Watch whether track IDs remain stable enough for temporal reasoning.
- Record obvious failure cases and verify `Q` / `Esc` exit behavior before merging Milestone 1.

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
