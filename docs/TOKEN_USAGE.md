# Token Usage

This document records token/cost usage for cloud or agentic components once they are introduced.

The local computer-vision pipeline should not require LLM tokens for every frame. Agentic calls should operate on structured events or selected evidence rather than continuous raw video whenever practical.

## Status

No token-using component implemented yet.

## Goals

- Keep routine perception local.
- Avoid one model call per frame.
- Measure tokens per event/session once AWS agentic components are added.
- Record approximate cost alongside latency and usefulness.
- Prefer deterministic local handling for time-critical alerts.

## Usage Template

### YYYY-MM-DD — Experiment / session

**Model / service**

- Provider:
- Model/service:
- Purpose:

**Usage**

| Metric | Value |
|---|---|
| Requests | |
| Input tokens | |
| Output tokens | |
| Total tokens | |
| Approx. cost | |
| Mean response latency | |

**Notes**

- Was the model call necessary?
- Could the same decision be made locally/deterministically?
- What evidence was sent?
- What should be changed next time?
