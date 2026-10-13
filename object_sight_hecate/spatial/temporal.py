from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any

from object_sight_hecate.spatial.position import SpatialObservation


@dataclass(frozen=True)
class TrackSample:
    timestamp: float
    normalized_x: float
    area_ratio: float


@dataclass(frozen=True)
class TemporalObservation:
    spatial: SpatialObservation
    timestamp: float
    horizontal_motion: str
    range_trend: str
    crossing_trajectory: str | None
    delta_x: float | None
    area_change_ratio: float | None
    sample_count: int


@dataclass(frozen=True)
class SpatialEvent:
    """Structured, model-agnostic output from temporal spatial reasoning."""

    schema_version: str
    timestamp: float
    source: str
    event_type: str
    track_id: int | None
    label: str
    confidence: float
    horizontal_position: str
    clock_position: int
    horizontal_motion: str
    range_trend: str
    crossing_trajectory: str | None
    delta_x: float | None
    area_change_ratio: float | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class TemporalTracker:
    """Maintain a short per-track history and estimate simple motion trends.

    Range trend is inferred from bounding-box area change. It is useful as an
    early monocular heuristic, but it is camera-motion-sensitive and should not
    yet be treated as a true distance measurement.
    """

    def __init__(
        self,
        history_size: int = 6,
        horizontal_threshold: float = 0.03,
        area_change_threshold: float = 0.10,
        max_track_age_s: float = 2.0,
    ) -> None:
        if history_size < 2:
            raise ValueError("history_size must be at least 2")
        if horizontal_threshold <= 0:
            raise ValueError("horizontal_threshold must be positive")
        if area_change_threshold <= 0:
            raise ValueError("area_change_threshold must be positive")
        if max_track_age_s <= 0:
            raise ValueError("max_track_age_s must be positive")

        self.history_size = history_size
        self.horizontal_threshold = horizontal_threshold
        self.area_change_threshold = area_change_threshold
        self.max_track_age_s = max_track_age_s
        self._history: dict[int, deque[TrackSample]] = {}

    def update(
        self,
        observation: SpatialObservation,
        frame_width: int,
        frame_height: int,
        timestamp: float | None = None,
    ) -> TemporalObservation:
        if frame_width <= 0 or frame_height <= 0:
            raise ValueError("frame dimensions must be positive")

        now = perf_counter() if timestamp is None else timestamp
        self._prune(now)

        detection = observation.detection
        track_id = detection.track_id
        if track_id is None:
            return TemporalObservation(
                spatial=observation,
                timestamp=now,
                horizontal_motion="unknown",
                range_trend="unknown",
                crossing_trajectory=None,
                delta_x=None,
                area_change_ratio=None,
                sample_count=0,
            )

        box_width = max(0, detection.x2 - detection.x1)
        box_height = max(0, detection.y2 - detection.y1)
        frame_area = frame_width * frame_height
        area_ratio = (box_width * box_height) / frame_area

        history = self._history.setdefault(track_id, deque(maxlen=self.history_size))
        history.append(
            TrackSample(
                timestamp=now,
                normalized_x=observation.normalized_x,
                area_ratio=area_ratio,
            )
        )

        if len(history) < 2:
            return TemporalObservation(
                spatial=observation,
                timestamp=now,
                horizontal_motion="unknown",
                range_trend="unknown",
                crossing_trajectory=None,
                delta_x=None,
                area_change_ratio=None,
                sample_count=len(history),
            )

        first = history[0]
        latest = history[-1]
        delta_x = latest.normalized_x - first.normalized_x

        if delta_x >= self.horizontal_threshold:
            horizontal_motion = "moving right"
        elif delta_x <= -self.horizontal_threshold:
            horizontal_motion = "moving left"
        else:
            horizontal_motion = "steady"

        if first.area_ratio <= 0:
            area_change_ratio = None
            range_trend = "unknown"
        else:
            area_change_ratio = (latest.area_ratio - first.area_ratio) / first.area_ratio
            if area_change_ratio >= self.area_change_threshold:
                range_trend = "approaching"
            elif area_change_ratio <= -self.area_change_threshold:
                range_trend = "receding"
            else:
                range_trend = "steady"

        crossing_trajectory = self._crossing_trajectory(history)

        return TemporalObservation(
            spatial=observation,
            timestamp=now,
            horizontal_motion=horizontal_motion,
            range_trend=range_trend,
            crossing_trajectory=crossing_trajectory,
            delta_x=delta_x,
            area_change_ratio=area_change_ratio,
            sample_count=len(history),
        )

    def to_event(
        self,
        observation: TemporalObservation,
        *,
        source: str = "camera-0",
    ) -> SpatialEvent:
        """Convert temporal state into a structured event for downstream layers."""
        spatial = observation.spatial
        detection = spatial.detection
        event_type = "crossing" if observation.crossing_trajectory else "track_update"

        return SpatialEvent(
            schema_version="1.0",
            timestamp=observation.timestamp,
            source=source,
            event_type=event_type,
            track_id=detection.track_id,
            label=detection.label,
            confidence=detection.confidence,
            horizontal_position=spatial.horizontal_position,
            clock_position=spatial.clock_position,
            horizontal_motion=observation.horizontal_motion,
            range_trend=observation.range_trend,
            crossing_trajectory=observation.crossing_trajectory,
            delta_x=observation.delta_x,
            area_change_ratio=observation.area_change_ratio,
        )

    @staticmethod
    def _crossing_trajectory(history: deque[TrackSample]) -> str | None:
        """Detect a full left-third <-> right-third crossing within recent history."""
        if len(history) < 3:
            return None

        first_x = history[0].normalized_x
        latest_x = history[-1].normalized_x

        if first_x < 1 / 3 and latest_x > 2 / 3:
            return "left_to_right"
        if first_x > 2 / 3 and latest_x < 1 / 3:
            return "right_to_left"
        return None

    def _prune(self, now: float) -> None:
        stale_ids = [
            track_id
            for track_id, history in self._history.items()
            if history and now - history[-1].timestamp > self.max_track_age_s
        ]
        for track_id in stale_ids:
            del self._history[track_id]
