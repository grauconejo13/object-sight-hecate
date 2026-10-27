"""Optional scene briefing: Hecate's structured detections -> one calm sentence via NVIDIA Nemotron.

Division of labour:
- YOLO + tracking + local alert rules run on the laptop and decide, in
  milliseconds, what must be spoken right now. That path never waits on this module.
- On request, Nemotron on Nebius Token Factory reads the *structured* scene
  (labels, clock directions, view-size trends, recent local alerts; never
  images) and summarises it as one short sentence a wearer can take in by ear.
- A local guard checks every model reply against the facts. Anything that
  claims identity, intent, danger, or distance, or mentions a direction that is
  not in the facts, is discarded in favour of a deterministic local summary.

Configuration (environment only; never commit keys):
    NEBIUS_API_KEY    required to enable Nemotron
    NEBIUS_MODEL      default nvidia/nemotron-3-super-120b-a12b
    NEBIUS_BASE_URL   default https://api.tokenfactory.nebius.com/v1
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable

DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b"
DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1"
REQUEST_TIMEOUT_S = 12.0
MIN_CONFIDENCE = 0.4
MAX_FACTS = 12
MAX_BRIEFING_CHARS = 220
CACHE_TTL_S = 10.0

VIEW_NAMES = {"backward": "Rear view", "forward": "Front view", "phone": "Camera view"}

SYSTEM_PROMPT = """You turn a wearable camera's object list into ONE short spoken sentence.

Rules:
- Start with the view name you are given, then a colon.
- Mention only objects in the facts, using their exact labels and their exact "o'clock" directions. Group repeats ("two people at 6 o'clock").
- Most relevant first: people, then vehicles and bikes, then animals, then other objects. Omit minor objects if the sentence gets long.
- You may say an object is "larger in view" or "smaller in view" only when its size_trend says so, and "crossed the view" only when crossed is true.
- Never describe identity, gender, age, appearance, emotion, intent, or behaviour ("following", "watching").
- Never say anything is dangerous, safe, suspicious, a threat, near, far, close, approaching, or give any distance.
- If there are no objects, say the view shows nothing detected.
- At most 25 words. Plain text only. No preamble."""

# Words the model must not use, whatever the facts say. Word-boundary matched.
FORBIDDEN_TERMS = (
    "danger", "dangerous", "unsafe", "safe", "safely", "threat", "threatening", "suspicious",
    "attack", "attacking", "aggressive", "angry", "hostile", "criminal", "intend", "intends",
    "intent", "intention", "wants", "trying", "following", "follows", "stalking", "watching",
    "near", "nearby", "close", "closer", "closing", "far", "approaching", "distance",
    "meter", "meters", "metre", "metres", "feet", "foot", "ft", "yard", "yards", "km", "miles",
    "man", "men", "woman", "women", "boy", "girl", "male", "female", "he", "she", "his", "her",
    "old", "young", "elderly", "child", "kid",
)
_FORBIDDEN_RE = re.compile(r"\b(" + "|".join(FORBIDDEN_TERMS) + r")\b", re.IGNORECASE)
_CLOCK_RE = re.compile(r"\b(\d{1,2})\s*o['’]?\s*clock\b", re.IGNORECASE)
_THINK_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)

PRIORITY = {"person": 0, "bicycle": 1, "motorcycle": 1, "car": 1, "bus": 1, "truck": 1, "dog": 2, "cat": 2}

PLURALS = {"person": "people", "bus": "buses", "knife": "knives"}


@dataclass(frozen=True)
class SceneFacts:
    view: str  # backward | forward | phone
    objects: tuple[dict[str, Any], ...]
    recent_changes: tuple[str, ...] = ()
    stale: bool = False

    @property
    def view_name(self) -> str:
        return VIEW_NAMES.get(self.view, "Camera view")

    @property
    def clocks(self) -> set[int]:
        return {obj["clock"] for obj in self.objects}

    def as_prompt_json(self) -> str:
        return json.dumps(
            {
                "view_name": self.view_name,
                "objects": list(self.objects),
                "recent_changes": list(self.recent_changes),
            },
            separators=(",", ":"),
        )

    def cache_key(self) -> str:
        return hashlib.sha256(self.as_prompt_json().encode()).hexdigest()


def _size_trend(observation: dict[str, Any]) -> str:
    trend = observation.get("range_trend") or observation.get("motion")
    if trend in ("approaching", "larger in view"):
        return "larger in view"
    if trend in ("receding", "smaller in view"):
        return "smaller in view"
    return "unchanged"


def build_facts(
    observations: list[dict[str, Any]],
    *,
    view: str,
    recent_alerts: list[dict[str, Any]] | None = None,
    stale: bool = False,
) -> SceneFacts:
    """Reduce raw detections to the small, model-agnostic fact set the LLM may use."""
    usable = []
    for obs in observations or []:
        try:
            confidence = float(obs["confidence"])
            clock = int(obs["clock"])
            label = str(obs["label"]).strip().lower()
        except (KeyError, TypeError, ValueError):
            continue
        if confidence < MIN_CONFIDENCE or not label or not 1 <= clock <= 12:
            continue
        usable.append({
            "label": label,
            "clock": clock,
            "size_trend": _size_trend(obs),
            "crossed": bool(obs.get("crossing")),
            "confidence": round(confidence, 2),
        })
    usable.sort(key=lambda o: (PRIORITY.get(o["label"], 3), -o["confidence"]))

    changes = []
    for alert in recent_alerts or []:
        label = str(alert.get("label", "")).lower()
        clock = alert.get("clock")
        if not label or not isinstance(clock, int):
            continue
        kind = alert.get("kind")
        if kind == "approaching":
            changes.append(f"{label} at {clock} o'clock grew larger in view")
        elif kind == "crossing":
            changes.append(f"{label} crossed the view")
        elif kind == "new":
            changes.append(f"{label} appeared at {clock} o'clock")
    return SceneFacts(view=view, objects=tuple(usable[:MAX_FACTS]), recent_changes=tuple(changes[-5:]), stale=stale)


def _plural(label: str, count: int) -> str:
    if count == 1:
        return f"a {label}" if label[0] not in "aeiou" else f"an {label}"
    word = PLURALS.get(label, label + "s")
    numbers = {2: "two", 3: "three", 4: "four", 5: "five"}
    return f"{numbers.get(count, str(count))} {word}"


def local_briefing(facts: SceneFacts) -> str:
    """Deterministic summary used when Nemotron is unavailable or its reply fails the guard."""
    if facts.stale:
        return f"{facts.view_name}: no current frame from the camera."
    if not facts.objects:
        return f"{facts.view_name}: nothing detected."
    groups = Counter((obj["label"], obj["clock"]) for obj in facts.objects)
    parts = []
    for (label, clock), count in groups.items():  # Insertion order = priority order.
        parts.append(f"{_plural(label, count)} at {clock} o'clock")
        if len(parts) == 4:
            break
    if len(parts) == 1:
        body = parts[0]
    else:
        body = ", ".join(parts[:-1]) + " and " + parts[-1]
    return f"{facts.view_name}: {body}."


def check_briefing(text: str, facts: SceneFacts) -> str | None:
    """Return a reason the reply is unacceptable, or None if it passes."""
    if not text:
        return "empty reply"
    if len(text) > MAX_BRIEFING_CHARS:
        return "reply too long"
    match = _FORBIDDEN_RE.search(text)
    if match:
        return f"used forbidden term '{match.group(0).lower()}'"
    if re.search(r"\d+(\.\d+)?\s*(m|cm|ft|km|mi)\b", text, re.IGNORECASE):
        return "stated a distance"
    for clock in _CLOCK_RE.findall(text):
        if int(clock) not in facts.clocks:
            return f"mentioned {clock} o'clock, which is not in the facts"
    return None


def clean_reply(content: str) -> str:
    text = _THINK_RE.sub("", content or "")
    if "</think>" in text.lower():  # Reasoning without an opening tag.
        text = text[text.lower().rindex("</think>") + len("</think>"):]
    text = text.strip().strip('"').strip()
    return " ".join(text.split())


Transport = Callable[[str, dict[str, str], bytes, float], tuple[int, bytes]]


def urllib_transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(256 * 1024)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(16 * 1024)


@dataclass
class Briefer:
    """Calls Nemotron on Token Factory; always returns a usable, guarded briefing."""

    api_key: str | None = None
    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    transport: Transport = urllib_transport
    clock: Callable[[], float] = time.monotonic
    _cache: dict[str, tuple[float, dict[str, Any]]] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    @classmethod
    def from_env(cls) -> "Briefer":
        return cls(
            api_key=os.getenv("NEBIUS_API_KEY") or None,
            model=os.getenv("NEBIUS_MODEL", DEFAULT_MODEL),
            base_url=os.getenv("NEBIUS_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        )

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def status(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "provider": "nebius-token-factory",
            "model": self.model if self.available else None,
            "reason": None if self.available else "NEBIUS_API_KEY is not set on the backend",
        }

    def brief(self, facts: SceneFacts) -> dict[str, Any]:
        base = {"view": facts.view_name, "object_count": len(facts.objects)}
        if facts.stale or not self.available:
            reason = "camera offline" if facts.stale else "NEBIUS_API_KEY is not set on the backend"
            return {**base, "text": local_briefing(facts), "provider": "local", "nebius": "unavailable" if not self.available else "skipped", "reason": reason}

        key = facts.cache_key()
        now = self.clock()
        with self._lock:
            cached = self._cache.get(key)
            if cached and now - cached[0] < CACHE_TTL_S:
                return {**cached[1], "cached": True}

        started = time.perf_counter()
        result = self._call_nemotron(facts)
        result["latency_ms"] = round((time.perf_counter() - started) * 1000)
        result = {**base, **result}
        if result["provider"] == "nemotron":
            with self._lock:
                self._cache[key] = (now, result)
                for stale_key in [k for k, (t, _) in self._cache.items() if now - t > CACHE_TTL_S]:
                    del self._cache[stale_key]
        return result

    def _call_nemotron(self, facts: SceneFacts) -> dict[str, Any]:
        body = json.dumps({
            "model": self.model,
            "temperature": 0.2,
            "max_tokens": 600,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": facts.as_prompt_json()},
            ],
        }).encode()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        def fallback(reason: str, nebius: str = "error") -> dict[str, Any]:
            return {"text": local_briefing(facts), "provider": "local", "nebius": nebius, "reason": reason}

        try:
            status, raw = self.transport(f"{self.base_url}/chat/completions", headers, body, REQUEST_TIMEOUT_S)
        except (OSError, TimeoutError) as exc:
            return fallback(f"Nebius unreachable: {type(exc).__name__}")
        if status == 401 or status == 403:
            return fallback("Nebius rejected the API key", "unavailable")
        if status == 429:
            return fallback("Nebius rate limit reached")
        if status >= 400:
            return fallback(f"Nebius returned HTTP {status}")
        try:
            content = json.loads(raw)["choices"][0]["message"].get("content") or ""
        except (ValueError, KeyError, IndexError, TypeError):
            return fallback("Unexpected response from Nebius")

        text = clean_reply(content)
        problem = check_briefing(text, facts)
        if problem:
            return fallback(f"Nemotron reply discarded by local guard: {problem}", "guarded")
        return {"text": text, "provider": "nemotron", "model": self.model, "nebius": "ok", "reason": None}
