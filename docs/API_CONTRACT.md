# API Contract

This document defines interfaces between Object-Sight Hecate components as they stabilize.

## Status

Milestone 2 introduced the first implemented structured spatial-event contract. Milestone 3 adds a deterministic awareness-decision contract that filters frame-by-frame state into quiet, watch, or notify outcomes.

## Goals

- Keep perception, spatial reasoning, alerting, and cloud integrations loosely coupled.
- Prefer structured events over passing raw model-specific objects between layers.
- Keep time-critical awareness logic local where practical.
- Avoid identity, intent, emotion, or trustworthiness inference.
- Version contracts when a breaking change becomes necessary.

## Spatial Event v1

`TemporalTracker.to_event(...)` converts a temporal observation into a model-agnostic `SpatialEvent`.

Example:

```json
{
  "schema_version": "1.0",
  "timestamp": 0.2,
  "source": "camera-0",
  "event_type": "crossing",
  "track_id": 6,
  "label": "person",
  "confidence": 0.9,
  "horizontal_position": "right",
  "clock_position": 3,
  "horizontal_motion": "moving right",
  "range_trend": "steady",
  "crossing_trajectory": "left_to_right",
  "delta_x": 0.7,
  "area_change_ratio": 0.0
}
```

### Event types

- `track_update` — ordinary tracked temporal state.
- `crossing` — a tracked object traversed from the left third to the right third, or the reverse, within the retained short history.

### Temporal fields

- `horizontal_motion`: `moving left`, `moving right`, `steady`, or `unknown`.
- `range_trend`: `approaching`, `receding`, `steady`, or `unknown`.
- `crossing_trajectory`: `left_to_right`, `right_to_left`, or `null`.
- `delta_x`: normalized horizontal displacement across the retained history.
- `area_change_ratio`: relative bounding-box area change across the retained history.

## Awareness Decision v1

`AwarenessEngine.evaluate(...)` consumes a `SpatialEvent` and returns a local deterministic relevance decision.

Example:

```json
{
  "schema_version": "1.0",
  "timestamp": 0.2,
  "source": "camera-0",
  "track_id": 6,
  "action": "notify",
  "priority": 2,
  "reason_codes": ["full_crossing"],
  "message": "Person crossing left to right.",
  "suppressed": false
}
```

### Actions

- `quiet` — no meaningful change worth surfacing.
- `watch` — keep observing locally; no user-facing notification yet.
- `notify` — surface a concise local cue.

Milestone 3 deliberately does **not** define an `urgent` action. The current monocular prototype does not yet have sufficiently strong depth/ego-motion evidence for a higher-consequence safety classification.

### Initial relevance rules

- Untracked or low-confidence detections remain `quiet`.
- Lateral movement becomes `watch`.
- Off-axis approaching movement becomes `watch`.
- High-confidence approaching movement directly ahead may become `notify`.
- A conservative full crossing may become `notify`.
- Duplicate notifications for the same track/event are suppressed during a short cooldown.

## Important limitations

`range_trend` is currently a monocular heuristic based on bounding-box area change. It is not a physical distance measurement. Camera motion, pose change, occlusion, and detector jitter can change the estimate. It must not be treated as sufficient evidence for consequential alerts.

Awareness decisions are relevance filters over observable geometry. They do not infer whether a person is dangerous, following the wearer, trustworthy, suspicious, or emotionally significant.

## Contracts To Define Later

- Directional audio / haptic output schema
- Multi-camera normalized observation schema
- Cloud / agent event envelope
- Human-confirmation response schema
