# API Contract

This document defines interfaces between Object-Sight Hecate components as they stabilize.

## Status

Milestone 2 introduces the first implemented structured spatial-event contract. It is internal and may still evolve before external integrations depend on it.

## Goals

- Keep perception, spatial reasoning, alerting, and cloud integrations loosely coupled.
- Prefer structured events over passing raw model-specific objects between layers.
- Keep time-critical safety logic local where practical.
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

## Important limitation

`range_trend` is currently a monocular heuristic based on bounding-box area change. It is not a physical distance measurement. Camera motion, pose change, occlusion, and detector jitter can change the estimate. It must not be treated as sufficient evidence for consequential alerts.

## Contracts To Define Later

- Alert / relevance event schema
- Multi-camera normalized observation schema
- Cloud / agent event envelope
- Human-confirmation response schema
