# Architecture and Product Decisions

This is a lightweight decision log for choices that materially affect Object-Sight Hecate.

## D-001 — Separate hackathon repository

**Date:** 2026-09-14  
**Status:** Accepted

`object-sight` remains the public computer-vision learning/demo repository. `object-sight-hecate` is the private OpenCV AI Competition build.

**Why:** Keeps the learning history clear while giving the hackathon project its own scope, architecture, and submission history.

## D-002 — User-initiated awareness sessions

**Date:** 2026-09-14  
**Status:** Accepted

Object-Sight should be deliberately turned on and off by the user rather than continuously monitoring by default.

**Why:** Better privacy, clearer product intent, and lower unnecessary compute/storage.

## D-003 — Describe situations, not character or intent

**Date:** 2026-09-14  
**Status:** Accepted

The system may describe observable movement, location, distance, trajectory, or persistence. It should not infer criminality, trustworthiness, personality, or emotion from appearance/body language.

## D-004 — Single-camera reliability before Hecate fusion

**Date:** 2026-09-14  
**Status:** Accepted

Prove the perception and tracking pipeline with one camera before adding a multi-camera rig.

## D-005 — Public Nebius x NVIDIA hackathon entry

**Date:** 2026-10-27  
**Status:** Accepted (supersedes the private-repository part of D-001)

**Decision**

Submit Hecate to the Nebius Global AI Hackathon with NVIDIA. The repository becomes public under the MIT License, and the cloud component is NVIDIA Nemotron on Nebius Token Factory (scene briefings) instead of the previously planned AWS layer.

**Why**

The hackathon requires a public, open-source repository and a project that runs on Nebius Token Factory or AI Cloud with an NVIDIA open model. Nemotron fits Hecate's existing plan for a cloud layer that summarises structured evidence without sitting on the time-critical alert path.

**Consequences / tradeoffs**

- Time-critical alerts stay local; Nemotron is on demand and its replies pass a local guard.
- Only structured facts are sent to Nebius, never images.
- Ultralytics YOLO is AGPL-3.0; Hecate's own code is MIT and the README says so.

## Decision Template

### D-XXX — Title

**Date:** YYYY-MM-DD  
**Status:** Proposed / Accepted / Rejected / Superseded

**Decision**


**Why**


**Consequences / tradeoffs**

