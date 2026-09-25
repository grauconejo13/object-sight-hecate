from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from object_sight_hecate.spatial.temporal import SpatialEvent


@dataclass(frozen=True)
class AwarenessDecision:
    """A conservative relevance decision derived from a structured spatial event."""

    schema_version: str
    timestamp: float
    source: str
    track_id: int | None
    action: str
    priority: int
    reason_codes: tuple[str, ...]
    message: str | None
    suppressed: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class AwarenessEngine:
    """Reduce noisy frame-by-frame observations into selective awareness outputs.

    Milestone 3 intentionally uses deterministic local rules. The engine does
    not infer identity, intent, danger, or trustworthiness. It only prioritizes
    observable motion/spatial cues from SpatialEvent v1.
    """

    def __init__(
        self,
        *,
        min_confidence: float = 0.40,
        notify_confidence: float = 0.55,
        cooldown_s: float = 1.5,
    ) -> None:
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be between 0 and 1")
        if not 0.0 <= notify_confidence <= 1.0:
            raise ValueError("notify_confidence must be between 0 and 1")
        if notify_confidence < min_confidence:
            raise ValueError("notify_confidence must be >= min_confidence")
        if cooldown_s < 0:
            raise ValueError("cooldown_s must be non-negative")

        self.min_confidence = min_confidence
        self.notify_confidence = notify_confidence
        self.cooldown_s = cooldown_s
        self._last_emitted: dict[tuple[int | None, str], float] = {}

    def evaluate(self, event: SpatialEvent) -> AwarenessDecision:
        reasons: list[str] = []

        if event.track_id is None:
            return self._decision(event, "quiet", 0, ("untracked",), None)

        if event.confidence < self.min_confidence:
            return self._decision(event, "quiet", 0, ("low_detection_confidence",), None)

        action = "quiet"
        priority = 0
        message: str | None = None

        if event.crossing_trajectory:
            action = "notify"
            priority = 2
            reasons.append("full_crossing")
            message = self._crossing_message(event)
        elif event.range_trend == "approaching":
            reasons.append("approaching")
            if event.confidence >= self.notify_confidence and event.clock_position == 12:
                action = "notify"
                priority = 2
                reasons.append("ahead")
                message = f"{event.label.capitalize()} approaching ahead."
            else:
                action = "watch"
                priority = 1
        elif event.horizontal_motion in {"moving left", "moving right"}:
            action = "watch"
            priority = 1
            reasons.append("lateral_motion")
        else:
            reasons.append("no_meaningful_change")

        suppressed = False
        if action == "notify":
            key = (event.track_id, self._notification_key(event))
            last = self._last_emitted.get(key)
            if last is not None and event.timestamp - last < self.cooldown_s:
                suppressed = True
                reasons.append("cooldown")
                action = "watch"
                priority = 1
                message = None
            else:
                self._last_emitted[key] = event.timestamp

        return self._decision(
            event,
            action,
            priority,
            tuple(reasons),
            message,
            suppressed=suppressed,
        )

    @staticmethod
    def _notification_key(event: SpatialEvent) -> str:
        if event.crossing_trajectory:
            return f"crossing:{event.crossing_trajectory}"
        if event.range_trend == "approaching":
            return f"approaching:{event.clock_position}"
        return event.event_type

    @staticmethod
    def _crossing_message(event: SpatialEvent) -> str:
        direction = {
            "left_to_right": "left to right",
            "right_to_left": "right to left",
        }.get(event.crossing_trajectory, "across view")
        return f"{event.label.capitalize()} crossing {direction}."

    @staticmethod
    def _decision(
        event: SpatialEvent,
        action: str,
        priority: int,
        reasons: tuple[str, ...],
        message: str | None,
        *,
        suppressed: bool = False,
    ) -> AwarenessDecision:
        return AwarenessDecision(
            schema_version="1.0",
            timestamp=event.timestamp,
            source=event.source,
            track_id=event.track_id,
            action=action,
            priority=priority,
            reason_codes=reasons,
            message=message,
            suppressed=suppressed,
        )
