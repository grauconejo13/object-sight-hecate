# Performance

This document tracks runtime performance, latency, resource use, and accuracy-related measurements for Object-Sight Hecate.

## Status

Initial single-camera baseline recorded on the project laptop. More formal benchmarking is still required.

## Metrics To Track

- Camera input resolution
- Frames per second
- Detector inference latency
- End-to-end alert latency
- Tracking latency
- CPU usage
- GPU usage when applicable
- Memory usage
- Dropped frames
- Multi-camera synchronization error
- Low-light performance
- False-positive / false-negative observations for selected scenarios

## 2026-09-15 — First live webcam baseline

**Environment**

- Device: project Windows laptop
- OS: Windows
- Python: 3.11.5
- OpenCV: 5.0.0
- Model: Ultralytics YOLO11n
- Camera / input: built-in webcam
- Resolution: 1280x720

**Results**

| Metric | Result |
|---|---|
| Observed FPS | ~13.3 FPS in the first captured run; value fluctuates during movement |
| Mean inference latency | Not yet measured |
| P95 inference latency | Not yet measured |
| End-to-end alert latency | Not yet applicable |
| CPU | Not yet measured |
| GPU | Not yet measured |
| Memory | Not yet measured |

**Spatial behavior observed**

- Centered subject -> `ahead (12 o'clock)`.
- Subject moved left -> `left (9 o'clock)`.
- Subject moved right -> `right (3 o'clock)`.
- Clock-position mapping changed correctly during the live test.
- Track IDs change when a subject fully leaves the frame and later re-enters. This is acceptable for the current tracker baseline and should not be treated as identity re-identification.

**Observed detection limitations / failure cases**

- A soda/pop can was sometimes classified as `cell phone`.
- An open book was detected as `book`, while the same book lying flat could be missed.
- A plant in a cup/pot changed between `cup` and `potted plant` as its pose/view changed.
- Exact class labels are therefore sensitive to angle, visibility, model classes, and confidence threshold.

These failures are retained as evaluation evidence rather than hidden. Future Hecate behavior should depend primarily on reliable observable motion and spatial relationships, not assume every object label is semantically correct.

## Benchmark Template

### YYYY-MM-DD — Benchmark name

**Environment**

- Device:
- OS:
- Python:
- OpenCV:
- Model:
- Camera / input:
- Resolution:

**Results**

| Metric | Result |
|---|---|
| Average FPS | |
| Mean inference latency | |
| P95 inference latency | |
| End-to-end alert latency | |
| CPU | |
| GPU | |
| Memory | |

**Notes / failure cases**

- 
