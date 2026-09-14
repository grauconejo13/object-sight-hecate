# API Contract

This document defines interfaces between Object-Sight Hecate components as they stabilize.

## Status

Pre-build. No stable public API exists yet.

## Goals

- Keep perception, spatial reasoning, alerting, and AWS integrations loosely coupled.
- Prefer structured events over passing raw model-specific objects between layers.
- Version contracts when a breaking change becomes necessary.

## Planned Event Shape

```json
{
  "event_id": "example-id",
  "timestamp": "ISO-8601",
  "source": "camera-0",
  "type": "observation",
  "confidence": 0.0,
  "spatial": {
    "clock_position": null,
    "distance_m": null,
    "approaching": null
  },
  "metadata": {}
}
```

The schema above is illustrative only and should not be treated as stable until implementation begins.

## Contracts To Define Later

- Camera / frame source interface
- Detection result schema
- Tracking state schema
- Spatial observation schema
- Alert event schema
- AWS event payloads
- Human-confirmation response schema
