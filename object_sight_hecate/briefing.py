"""Optional scene briefing: Hecate's structured detections -> one calm sentence via NVIDIA Nemotron.

Division of labour:
- YOLO + tracking + local alert rules run on the laptop and decide, in
  milliseconds, what must be spoken right now. That path never waits on this module.
- On request, Nemotron on Nebius Token Factory reads the *structured* scene
  (labels, clock directions, view-size trends, recent local alerts; never
  images) and summarises it as one short sentence a wearer can take in by ear.
- A local guard checks every model reply against the facts. Anything that
  claims identity, intent, danger, or distance, names an object that is not in
  the facts, puts an object at a direction or count the facts do not support,
  or mentions a direction that is not in the facts, is discarded in favour of a
  deterministic local summary.

Configuration (environment only; never commit keys):
    NEBIUS_API_KEY    required to enable Nemotron
    NEBIUS_MODEL      default nvidia/nemotron-3-super-120b-a12b
    NEBIUS_BASE_URL   default https://api.tokenfactory.nebius.com/v1
"""

from __future__ import annotations

import hashlib
import json
import logging
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
# "9 and 12 o'clock", "5, 6 or 7 o'clock": several directions sharing one "o'clock".
_CLOCK_LIST_RE = re.compile(
    r"\b(\d{1,2}(?:\s*(?:,|and|or|&)\s*\d{1,2})+)\s*o['’]?\s*clock\b", re.IGNORECASE
)
log = logging.getLogger("uvicorn.error")
_THINK_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)

PRIORITY = {"person": 0, "bicycle": 1, "motorcycle": 1, "car": 1, "bus": 1, "truck": 1, "dog": 2, "cat": 2}

PLURALS = {"person": "people", "bus": "buses", "knife": "knives"}

# --- Object grounding --------------------------------------------------------
# Every object word in a reply must refer to something in the facts. The
# vocabulary is YOLO's COCO classes plus the synonyms a language model tends to
# use, and common scene nouns YOLO cannot detect (always rejected: the facts can
# never contain them, so naming one is invention).

COCO_LABELS = (
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog",
    "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
    "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
    "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle",
    "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant",
    "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard", "cell phone",
    "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors",
    "teddy bear", "hair drier", "toothbrush",
)
_ANIMALS = frozenset({"bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe"})
_VEHICLES = frozenset({"car", "bus", "truck", "motorcycle"})
_SYNONYMS: dict[str, frozenset[str]] = {
    "people": frozenset({"person"}), "persons": frozenset({"person"}),
    "pedestrian": frozenset({"person"}), "pedestrians": frozenset({"person"}),
    "someone": frozenset({"person"}), "somebody": frozenset({"person"}),
    "figure": frozenset({"person"}), "figures": frozenset({"person"}),
    "individual": frozenset({"person"}), "individuals": frozenset({"person"}), "crowd": frozenset({"person"}),
    "cyclist": frozenset({"bicycle"}), "cyclists": frozenset({"bicycle"}),
    "bike": frozenset({"bicycle", "motorcycle"}), "bikes": frozenset({"bicycle", "motorcycle"}),
    "motorbike": frozenset({"motorcycle"}), "motorbikes": frozenset({"motorcycle"}),
    "motorcyclist": frozenset({"motorcycle"}), "motorcyclists": frozenset({"motorcycle"}),
    "vehicle": _VEHICLES, "vehicles": _VEHICLES,
    "van": frozenset({"car", "truck"}), "vans": frozenset({"car", "truck"}),
    "lorry": frozenset({"truck"}), "lorries": frozenset({"truck"}), "suv": frozenset({"car"}), "suvs": frozenset({"car"}),
    "animal": _ANIMALS, "animals": _ANIMALS, "puppy": frozenset({"dog"}),
    "phone": frozenset({"cell phone"}), "phones": frozenset({"cell phone"}),
    "television": frozenset({"tv"}), "sofa": frozenset({"couch"}),
    "table": frozenset({"dining table"}), "tables": frozenset({"dining table"}),
    "plant": frozenset({"potted plant"}), "plants": frozenset({"potted plant"}),
    "bag": frozenset({"handbag", "backpack", "suitcase"}), "bags": frozenset({"handbag", "backpack", "suitcase"}),
    "ball": frozenset({"sports ball"}), "ski": frozenset({"skis"}),
}
_UNDETECTABLE = (
    "tree", "trees", "building", "buildings", "wall", "walls", "pole", "poles", "fence", "fences",
    "road", "street", "sidewalk", "path", "trail", "door", "doors", "window", "windows", "house",
    "houses", "stroller", "strollers", "wheelchair", "wheelchairs", "scooter", "scooters",
    "shadow", "shadows", "vegetation", "bush", "bushes", "post", "posts", "sign", "signs",
)
_IRREGULAR_PLURALS = {"person": "people", "knife": "knives", "mouse": "mice", "sheep": "sheep", "skis": "skis"}


def _surface_forms() -> dict[str, frozenset[str]]:
    forms: dict[str, frozenset[str]] = {}
    for label in COCO_LABELS:
        for form in {label, label + "s", label + "es", _IRREGULAR_PLURALS.get(label, label)}:
            forms[form] = frozenset({label})
    forms.update(_SYNONYMS)
    for word in _UNDETECTABLE:
        forms.setdefault(word, frozenset())
    return forms


_OBJECT_FORMS = _surface_forms()
_OBJECT_RE = re.compile(
    r"\b(" + "|".join(re.escape(f) for f in sorted(_OBJECT_FORMS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_COUNT_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
                "ten": 10, "several": 2, "multiple": 2, "many": 3}
_COUNT_RE = re.compile(r"\b(\d+|" + "|".join(_COUNT_WORDS) + r")\s+$", re.IGNORECASE)
_CLOCK_TOKEN_RE = re.compile(r"§(\d+)§")


def _clock_tokens(text: str) -> str:
    """Replace every o'clock mention with §N§ tokens, expanding lists like "9 and 12 o'clock"."""
    text = _CLOCK_LIST_RE.sub(
        lambda m: " ".join(f"§{int(n)}§" for n in re.findall(r"\d{1,2}", m.group(1))), text
    )
    return _CLOCK_RE.sub(lambda m: f" §{int(m.group(1))}§ ", text)


def _check_objects(text: str, facts: SceneFacts) -> str | None:
    """Every object named must be in the facts, at the direction and count claimed.

    Within a clause, a direction applies to every object named since the
    previous direction: "a person and a car at 7 o'clock" places both at 7.
    Directions listed together ("two people at 9 and 12 o'clock") are checked
    as one group: the objects may be spread across them.
    """
    body = text.split(":", 1)[1] if ":" in text else text
    # Hide "N o'clock" so the COCO label "clock" cannot match inside it.
    body = _clock_tokens(body)
    present = Counter(obj["label"] for obj in facts.objects)
    at_clock: dict[int, Counter[str]] = {}
    for obj in facts.objects:
        at_clock.setdefault(obj["clock"], Counter())[obj["label"]] += 1

    def check_group(pending: list[tuple[str, int]], clocks: list[int]) -> str | None:
        if not pending:
            return f"gave {clocks[0]} o'clock without naming a detected object"
        for word, claimed in pending:
            available = sum(at_clock.get(c, Counter())[label] for c in clocks for label in _OBJECT_FORMS[word])
            if available == 0:
                where = " or ".join(str(c) for c in clocks)
                return f"placed '{word}' at {where} o'clock, which the scene facts do not"
            if claimed > available:
                where = "/".join(str(c) for c in clocks)
                return f"claimed {claimed} '{word}' at {where} o'clock; the scene facts have {available}"
        for c in clocks:
            here = at_clock.get(c, Counter())
            if not any(here[label] for word, _ in pending for label in _OBJECT_FORMS[word]):
                return f"placed '{pending[0][0]}' at {c} o'clock, which the scene facts do not"
        return None

    for clause in re.split(r"[;.]", body):
        pending: list[tuple[str, int]] = []
        group: list[int] = []
        tokens = sorted(
            [(m.start(), "object", m) for m in _OBJECT_RE.finditer(clause)]
            + [(m.start(), "clock", m) for m in _CLOCK_TOKEN_RE.finditer(clause)],
            key=lambda item: item[0],
        )
        for _, kind, match in tokens:
            if kind == "clock":
                group.append(int(match.group(1)))
                continue
            if group:  # an object after a run of directions closes that run
                problem = check_group(pending, group)
                if problem:
                    return problem
                pending, group = [], []
            word = match.group(1).lower()
            labels = _OBJECT_FORMS[word]
            if not labels or not labels & present.keys():
                return f"named '{word}', which is not in the scene facts"
            count = _COUNT_RE.search(clause[: match.start()])
            claimed = 1
            if count:
                raw = count.group(1).lower()
                claimed = int(raw) if raw.isdigit() else _COUNT_WORDS[raw]
                if claimed > sum(present[label] for label in labels):
                    return f"claimed {raw} '{word}', more than the scene facts contain"
            pending.append((word, claimed))
        if group:
            problem = check_group(pending, group)
            if problem:
                return problem
    return None


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
    for clock in re.findall(r"§(\d+)§", _clock_tokens(text)):
        if int(clock) not in facts.clocks:
            return f"mentioned {clock} o'clock, which is not in the facts"
    return _check_objects(text, facts)


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

    def _request_body(self, facts: SceneFacts, *, thinking_off: bool) -> bytes:
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": facts.as_prompt_json()},
            ],
        }
        if thinking_off:
            # Nemotron 3 reasons before answering by default; one spoken sentence
            # doesn't need it, and reasoning can use up the whole token budget.
            payload["chat_template_kwargs"] = {"enable_thinking": False}
            payload["max_tokens"] = 200
        else:
            payload["max_tokens"] = 1500
        return json.dumps(payload).encode()

    def _call_nemotron(self, facts: SceneFacts) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        def fallback(reason: str, nebius: str = "error") -> dict[str, Any]:
            log.warning("Scene briefing fell back to the local summary: %s", reason)
            return {"text": local_briefing(facts), "provider": "local", "nebius": nebius, "reason": reason}

        url = f"{self.base_url}/chat/completions"
        try:
            status, raw = self.transport(url, headers, self._request_body(facts, thinking_off=True), REQUEST_TIMEOUT_S)
            if status in (400, 422):
                # The endpoint may not accept chat_template_kwargs; retry with a larger budget instead.
                status, raw = self.transport(url, headers, self._request_body(facts, thinking_off=False), REQUEST_TIMEOUT_S)
        except (OSError, TimeoutError) as exc:
            return fallback(f"Nebius unreachable: {type(exc).__name__}")
        if status == 401 or status == 403:
            return fallback("Nebius rejected the API key", "unavailable")
        if status == 429:
            return fallback("Nebius rate limit reached")
        if status >= 400:
            return fallback(f"Nebius returned HTTP {status}")
        try:
            choice = json.loads(raw)["choices"][0]
            content = choice["message"].get("content") or ""
        except (ValueError, KeyError, IndexError, TypeError):
            return fallback("Unexpected response from Nebius")

        text = clean_reply(content)
        if not text:
            cut = " (reply cut off by the token limit)" if choice.get("finish_reason") == "length" else ""
            return fallback(f"Nemotron returned no answer text{cut}", "guarded")
        problem = check_briefing(text, facts)
        if problem:
            log.warning("Nemotron reply rejected (%s): %r", problem, text[:300])
            return fallback(f"Nemotron reply discarded by local guard: {problem}", "guarded")
        return {"text": text, "provider": "nemotron", "model": self.model, "nebius": "ok", "reason": None}
