# Tasks

Working checklist for Object-Sight Hecate development.

Use this file to track milestone progress, validation work, and the next concrete build step. Check items only after they are implemented **and** verified where verification is required.

## Milestone 1 — Single-Camera Perception

- [x] Camera/video input, detection, tracking IDs, overlays, and OpenCV 5 runtime.
- [x] Left / ahead / right spatial mapping with initial 9 / 12 / 3 o'clock hints.
- [x] Spatial unit tests and local webcam validation.
- [x] Baseline performance and failure cases documented.
- [x] Milestone 1 PR merged into `main`.

**Milestone 1 status: Complete and merged.**

---

## Milestone 2 — Temporal Spatial Awareness

### Implementation

- [x] Bounded short history per track ID.
- [x] Horizontal motion: `moving left`, `moving right`, `steady`, `unknown`.
- [x] Initial monocular approaching / receding heuristic from bounding-box area change.
- [x] Stale-track pruning.
- [x] Full left-third <-> right-third crossing trajectories.
- [x] Versioned `SpatialEvent` output.
- [x] Unit/scenario tests for temporal behavior, crossing, and event payloads.

### Local validation still required

- [ ] Run complete unit-test suite on project laptop.
- [ ] Confirm Milestone 1 behavior still works.
- [ ] Validate left/right motion, stationary behavior, approach/recede, and full crossings.
- [ ] Record false transitions, FPS impact, latency, and failure cases.
- [ ] Tune thresholds only if observed behavior justifies it.
- [ ] Mark Milestone 2 PR ready and merge after validation.

**Milestone 2 status: Implementation complete; live validation pending.**

---

## Milestone 3 — Selective Awareness Engine

This branch is intentionally stacked on Milestone 2 because it consumes `SpatialEvent` v1.

### Implementation

- [x] Create `feature/selective-awareness-engine` branch.
- [x] Add deterministic local `AwarenessEngine`.
- [x] Add `quiet`, `watch`, and `notify` actions.
- [x] Keep low-confidence and untracked observations quiet.
- [x] Treat ordinary lateral motion as watch-only.
- [x] Treat off-axis approaching state as watch-only.
- [x] Allow high-confidence approaching-ahead state to notify.
- [x] Allow conservative full-crossing events to notify.
- [x] Add per-track/event cooldown suppression for duplicate notifications.
- [x] Add versioned `AwarenessDecision` output with reason codes and optional concise message.
- [x] Integrate awareness decisions into the live overlay.
- [x] Add unit tests for quiet/watch/notify routing, cooldowns, independent tracks, and serialization.
- [x] Document Awareness Decision v1.

### Safety / scope boundary

- [x] Do not infer identity, intent, danger, emotion, suspicion, or trustworthiness.
- [x] Do not add an `urgent` classification yet; current monocular range evidence is not strong enough for consequential safety classification.
- [x] Keep rules local and deterministic before adding cloud/agent reasoning.

### Local validation required

- [ ] Run the complete unit-test suite.
- [ ] Confirm steady tracked subjects remain mostly `quiet`.
- [ ] Confirm lateral movement becomes `watch` without user-facing message spam.
- [ ] Confirm a full crossing emits one `notify` then respects cooldown suppression.
- [ ] Confirm high-confidence approach directly ahead can notify.
- [ ] Confirm off-axis approach remains `watch`.
- [ ] Observe multiple tracks and verify cooldown isolation.
- [ ] Record alert precision / false-notification cases.
- [ ] Record FPS impact relative to Milestone 2.

### Milestone 3 exit criteria

- [ ] Quiet is demonstrably the common output for uninteresting steady state.
- [ ] Notify events are sparse and understandable.
- [ ] Duplicate cue suppression works in live use.
- [ ] No intent or danger inference is introduced.
- [ ] Performance remains acceptable for prototype use.

**Milestone 3 status: Implementation slice complete; live validation pending.**

---

## Later Milestones

- [ ] Directional audio and/or haptic cues.
- [ ] Multi-camera Hecate architecture.
- [ ] Low-light / adaptive capture experiments.
- [ ] AWS competition adapter.
- [ ] Nebius / NVIDIA competition adapter.
- [ ] Agentic perception -> decision -> action loop for non-time-critical follow-up.
- [ ] Human-confirmation workflow where appropriate.
- [ ] Evaluation dataset / repeatable scenario suite.
- [ ] Final architecture diagram.
- [ ] Final technical report.
- [ ] Judge demo / video preparation.

## Current next action

On the project laptop, validate Milestone 2 first, then switch to `feature/selective-awareness-engine` and run the Milestone 3 awareness scenarios before tuning relevance thresholds or adding audio/cloud outputs.
