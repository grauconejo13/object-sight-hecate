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

**What worked**

- Repository now has a complete code path from frame source -> detection/tracking -> spatial observation -> visual overlay.
- OpenCV 5 is explicitly required at runtime so an accidental OpenCV 4 environment fails clearly.
- Local repository sync and branch setup completed successfully.
- Python 3.11.5 virtual environment activated successfully.
- `pip` upgraded successfully before dependency installation.

**Problems / failures**

- Dependency installation stopped while installing the PyTorch dependency with `OSError: [Errno 28] No space left on device`.
- Because the dependency install did not complete, OpenCV runtime, tests, webcam capture, and model loading have not yet been validated locally.
- No trajectory, distance, relevance scoring, selective alerts, or AWS behavior exists yet.

**Evidence / measurements**

- Local Python version: `3.11.5`.
- OpenCV 5 and other packages downloaded, but the full environment did not finish installing because the system drive ran out of space.
- FPS is displayed at runtime for the first local benchmark once installation succeeds.

**Next step**

- Check available disk space and free enough room for the remaining ML dependencies.
- Rerun `pip install -r requirements.txt` after cleanup.
- Only after installation succeeds, run the unit tests and first webcam baseline.

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
