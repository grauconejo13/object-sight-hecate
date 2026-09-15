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

**What worked**

- Repository now has a complete code path from frame source -> detection/tracking -> spatial observation -> visual overlay.
- OpenCV 5 is explicitly required at runtime so an accidental OpenCV 4 environment fails clearly.

**Problems / failures**

- Camera behavior and model runtime have not yet been exercised on the project laptop; the GitHub-side build cannot access the user's webcam.
- No trajectory, distance, relevance scoring, selective alerts, or AWS behavior exists yet.

**Evidence / measurements**

- FPS is displayed at runtime for the first local benchmark.
- Spatial utility tests are included, but local execution is still required.

**Next step**

- Run the branch locally with a webcam and record baseline FPS, detection stability, and obvious failure cases.
- Fix any environment/runtime issues before adding temporal trajectory state.

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
