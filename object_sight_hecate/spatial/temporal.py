from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from time import perf_counter

from object_sight_hecate.spatial.position import SpatialObservation


@dataclass(frozen=True)
class TrackSample:
    timestamp: float
    normalized_x: float
    area_ratio: float


@dataclass(frozen=True)
class TemporalObservation:
    spatial: SpatialObservation
    horizontal_motion: str
    range_trend: str
    delta_x: float | None
    area_change_ratio: float | None
    sample_count: int


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
                horizontal_motion="unknown",
                range_trend="unknown",
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
                horizontal_motion="unknown",
                range_trend="unknown",
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

        return TemporalObservation(
            spatial=observation,
            horizontal_motion=horizontal_motion,
            range_trend=range_trend,
            delta_x=delta_x,
            area_change_ratio=area_change_ratio,
            sample_count=len(history),
        )

    def _prune(self, now: float) -> None:
        stale_ids = [
            track_id
            for track_id, history in self._history.items()
            if history and now - history[-1].timestamp > self.max_track_age_s
        ]
        for track_id in stale_ids:
            del self._history[track_id]
