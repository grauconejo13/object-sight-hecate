# Scene briefing with NVIDIA Nemotron on Nebius Token Factory

**Ask Hecate** (the ✦ button) turns what Hecate is tracking right now into one short spoken sentence, for example:

> Rear view: a person at 6 o'clock and a car at 7 o'clock.

It is optional and on demand. Live detection and the ESP32's spoken alerts never wait for it.

## Why a language model, and why here

YOLO and the tracker answer "what is in this frame, and where is each box?" in milliseconds. The local alert rules decide what must interrupt the wearer *now*. Neither produces the thing a person walking with a phone in their pocket wants when they ask "what's behind me?": a single, calm, prioritised sentence they can take in by ear.

Nemotron does that aggregation step:

- **Prioritises:** people first, then vehicles and bikes, then animals, then everything else; drops minor objects when the sentence would get long.
- **Groups:** "two people at 6 o'clock" rather than two separate track readouts.
- **Folds in recent history:** it also receives the last 30 s of local alerts ("bicycle crossed the view"), so the briefing covers change, not only the current frame.
- **Speaks plainly:** the result is short enough for speech synthesis.

What Nemotron never receives: images, bounding boxes, or track IDs. It gets labels, clock directions, a view-size trend, and recent changes. That keeps the cloud call small, fast, and private.

## Guardrails

The model is instructed to stay cautious, and a local guard **checks every reply before it is shown or spoken**. The reply is discarded, and a deterministic local summary is used instead, if it:

- names an object that is not in the facts: any YOLO class, common synonym ("pedestrian", "vehicle", "bike"), or a scene noun YOLO cannot detect ("tree", "scooter"). A valid direction is not enough: "a person at 6 o'clock" is rejected unless a person is in the facts
- places an object at a direction the facts do not give it. A direction applies to every object named before it in the clause, so "a person and a car at 7 o'clock" fails if the person is at 6
- gives a direction without naming a detected object ("something at 6 o'clock")
- claims more of an object than the facts contain, overall or at that direction ("two people at 6 o'clock" with one there)
- describes identity, gender, age, emotion, intent, or behaviour ("man", "following", "watching")
- makes a safety judgement ("dangerous", "safe", "suspicious", "threat")
- claims distance or motion toward the wearer ("near", "close", "approaching", "3 m")
- mentions an o'clock direction that is not in the facts
- is longer than 220 characters

The app labels which path produced the sentence:

| Tag under the briefing | Meaning |
| --- | --- |
| `NVIDIA Nemotron on Nebius · 1.2 s` | Nemotron reply, passed the guard |
| `Nemotron reply withheld by safety check · local summary` | Guard rejected the reply |
| `Nebius unavailable · local summary` | No API key, or Nebius rejected it |
| `Nebius error · local summary` | Network error, timeout, rate limit, or 5xx |
| `Camera offline · local summary` | ESP32 has not sent a frame for 6 s (no cloud call made) |

Hovering or long-pressing the ✦ button also shows whether Nebius is configured.

## Configure

1. Create an API key in the [Nebius Token Factory](https://tokenfactory.nebius.com/) console.
2. Set it **on the backend only** (the laptop running FastAPI). Never in `web/.env*`: Vite variables ship in public browser code.

```powershell
$env:NEBIUS_API_KEY = "paste-your-key"
# Optional overrides:
# $env:NEBIUS_MODEL = "nvidia/nemotron-3-super-120b-a12b"
# $env:NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1"
uvicorn object_sight_hecate.web_api:app --host 127.0.0.1 --port 8000
```

3. Check it: `curl http://127.0.0.1:8000/v1/briefing/status` should show `"available": true` and the model. The key itself is never returned.

| Variable | Default | Purpose |
| --- | --- | --- |
| `NEBIUS_API_KEY` | none | Enables Nemotron. Without it, briefings use the local summary. |
| `NEBIUS_MODEL` | `nvidia/nemotron-3-super-120b-a12b` | Any Nemotron chat model listed in Token Factory. |
| `NEBIUS_BASE_URL` | `https://api.tokenfactory.nebius.com/v1` | OpenAI-compatible endpoint. |

## API

- `GET /v1/briefing/status` → `{available, provider, model, reason}`
- `POST /v1/briefing` with `{"source": "esp32"}` (uses the wearable camera's latest tracked frame and recent alerts) or `{"source": "phone", "observations": [...]}` (the detections the phone app last received).

Response: `{text, provider: "nemotron" | "local", nebius, reason, model?, latency_ms?, cached?, view, object_count}`.

Identical scenes within 10 s are served from a small cache so repeated taps do not spend tokens.

## Tests

`tests/test_briefing.py` mocks the Token Factory transport and covers: request shape (URL, bearer key, model, no images or boxes), guard rejections (including invented objects at valid directions, wrong directions, inflated counts, and a check that every local summary passes the guard), reasoning-tag stripping, HTTP and network failures, caching, the offline camera path, and the API endpoints. `web/tests/briefing.test.js` covers the request payload and the provenance tags. No test calls the real API.
