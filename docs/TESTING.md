# Testing

This document tracks the test strategy and evaluation scenarios for Object-Sight Hecate.

## Principles

- Test observable behavior, not only model outputs.
- Record failure cases rather than hiding them.
- Separate perception accuracy from alert-policy quality.
- Re-test important scenarios under different lighting, motion, and camera angles.
- Avoid claims that are not supported by measured evidence.

## Planned Test Layers

### Unit tests

- Spatial utility functions
- Clock-position mapping
- Trajectory calculations
- Alert-threshold logic
- Event schema validation

### Integration tests

- Camera -> detection
- Detection -> tracking
- Tracking -> spatial observation
- Spatial observation -> alert decision
- Local event -> AWS workflow

### Scenario tests

Candidate scenarios:

- Pedestrian/cyclist approaching from rear-left
- Obstacle entering walking path
- User walking vs jogging
- Low-light street scene
- Trail scene with uneven terrain/obstacles
- Busy environment where the correct behavior is silence

## Test Case Template

### T-XXX — Scenario

**Setup**


**Expected behavior**


**Observed behavior**


**Result:** Pass / Fail / Partial

**Failure notes / evidence**

- 
