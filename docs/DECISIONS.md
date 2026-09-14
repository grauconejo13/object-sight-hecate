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

## Decision Template

### D-XXX — Title

**Date:** YYYY-MM-DD  
**Status:** Proposed / Accepted / Rejected / Superseded

**Decision**


**Why**


**Consequences / tradeoffs**

