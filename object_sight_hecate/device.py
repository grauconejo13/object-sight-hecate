"""Wearable ESP32 camera session: pushed frames -> tracking -> wearer-relative alerts.

The ESP32 cannot be reached from the laptop when it rides on the phone's hotspot,
so it pushes JPEG frames to the backend. Only the newest frame and its analysis
are held in memory; nothing is written to disk.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import asdict, dataclass, replace
from threading import Lock
from typing import Any, Callable, Protocol

import cv2
import numpy as np

from object_sight_hecate.spatial.position import SpatialObservation
from object_sight_hecate.spatial.temporal import TemporalObservation, TemporalTracker
from object_sight_hecate.vision.detector import Detection

FRAME_SIZES = ("QVGA", "VGA", "SVGA", "HD")
INTERVALS_MS = (150, 250, 400, 600, 1000, 2000)
MOUNTINGS = ("backward", "forward")
ONLINE_WINDOW_S = 6.0
MAX_FRAME_PIXELS = 3_000_000

# Objects worth interrupting someone for. Everything else stays on screen only.
ALERT_LABELS = {"person", "bicycle", "motorcycle", "car", "bus", "truck", "dog"}
ALERT_MIN_CONFIDENCE = 0.5
ALERT_MIN_SAMPLES = 4
TRACK_ALERT_COOLDOWN_S = 20.0
GLOBAL_ALERT_COOLDOWN_S = 4.0
NEW_TRACK_MEMORY_S = 600.0


class Tracker(Protocol):
    def track(self, frame: np.ndarray) -> list[Detection]: ...


@dataclass(frozen=True)
class DeviceSettings:
    """Camera settings the phone edits and the ESP32 applies on its next request."""

    frame_size: str = "VGA"
    jpeg_quality: int = 12  # ESP32 scale: lower is better quality, larger files.
    interval_ms: int = 400
    vflip: bool = False
    hmirror: bool = False
    mounting: str = "backward"
    paused: bool = False

    def validated(self) -> "DeviceSettings":
        if self.frame_size not in FRAME_SIZES:
            raise ValueError(f"frame_size must be one of {', '.join(FRAME_SIZES)}")
        if not 8 <= int(self.jpeg_quality) <= 40:
            raise ValueError("jpeg_quality must be between 8 and 40")
        if int(self.interval_ms) not in INTERVALS_MS:
            raise ValueError(f"interval_ms must be one of {INTERVALS_MS}")
        if self.mounting not in MOUNTINGS:
            raise ValueError("mounting must be 'backward' or 'forward'")
        return replace(
            self,
            jpeg_quality=int(self.jpeg_quality),
            interval_ms=int(self.interval_ms),
            vflip=bool(self.vflip),
            hmirror=bool(self.hmirror),
            paused=bool(self.paused),
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def as_headers(self) -> dict[str, str]:
        """Compact form the firmware reads without a JSON library."""
        return {
            "X-Hecate-Frame-Size": self.frame_size,
            "X-Hecate-Quality": str(self.jpeg_quality),
            "X-Hecate-Interval-Ms": str(self.interval_ms),
            "X-Hecate-Vflip": "1" if self.vflip else "0",
            "X-Hecate-Hmirror": "1" if self.hmirror else "0",
            "X-Hecate-Paused": "1" if self.paused else "0",
        }


def wearer_direction(normalized_x: float, mounting: str) -> tuple[str, int]:
    """Map image x (0 = image left) to a direction around the wearer.

    A backward-facing camera sees the world mirrored relative to the wearer:
    the left side of its image is behind the wearer's right shoulder.
    """
    x = min(max(normalized_x, 0.0), 1.0)
    if mounting == "backward":
        if x < 1 / 3:
            return "behind right", 5
        if x > 2 / 3:
            return "behind left", 7
        return "behind", 6
    if x < 1 / 3:
        return "left", 9
    if x > 2 / 3:
        return "right", 3
    return "ahead", 12


def _spoken_label(label: str) -> str:
    return label[:1].upper() + label[1:]


class DeviceSession:
    """Holds the newest pushed frame, its analysis, and alert history for one device."""

    def __init__(
        self,
        detector_factory: Callable[[], Tracker],
        *,
        clock: Callable[[], float] = time.monotonic,
        source: str = "esp32-0",
    ) -> None:
        self._detector_factory = detector_factory
        self._detector: Tracker | None = None
        self._clock = clock
        self._lock = Lock()
        self.source = source
        self.settings = DeviceSettings()
        self._tracker = TemporalTracker(history_size=6, max_track_age_s=3.0)
        self._jpeg: bytes | None = None
        self._result: dict[str, Any] | None = None
        self._seq = 0
        self._last_seen: float | None = None
        self._frame_times: deque[float] = deque(maxlen=12)
        self._alerts: deque[dict[str, Any]] = deque(maxlen=20)
        self._next_alert_id = 1
        self._alerted: dict[tuple[int, str], float] = {}
        self._last_alert_at = float("-inf")

    # --- device side -----------------------------------------------------

    def heartbeat(self) -> DeviceSettings:
        with self._lock:
            self._last_seen = self._clock()
            return self.settings

    def ingest(self, jpeg: bytes) -> DeviceSettings:
        frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("Body must be a valid JPEG")
        height, width = frame.shape[:2]
        if width * height > MAX_FRAME_PIXELS:
            raise ValueError("Frame exceeds the 3 megapixel limit")

        with self._lock:
            now = self._clock()
            if self._detector is None:
                self._detector = self._detector_factory()
            start = time.perf_counter()
            detections = self._detector.track(frame)
            inference_ms = round((time.perf_counter() - start) * 1000)

            observations = []
            new_alerts = []
            for detection in detections:
                center_x, _ = detection.center
                normalized_x = min(max(center_x / width, 0.0), 1.0)
                position, clock_position = wearer_direction(normalized_x, self.settings.mounting)
                spatial = SpatialObservation(
                    detection=detection,
                    horizontal_position=position,
                    clock_position=clock_position,
                    normalized_x=normalized_x,
                )
                temporal = self._tracker.update(spatial, width, height, timestamp=now)
                event = self._tracker.to_event(temporal, source=self.source).as_dict()
                observations.append({
                    "label": detection.label,
                    "confidence": round(detection.confidence, 3),
                    "box": [detection.x1, detection.y1, detection.x2, detection.y2],
                    "position": position,
                    "clock": clock_position,
                    "track_id": detection.track_id,
                    "motion": temporal.horizontal_motion,
                    "range_trend": temporal.range_trend,
                    "crossing": temporal.crossing_trajectory,
                    "samples": temporal.sample_count,
                    "event": event,
                })
                alert = self._maybe_alert(temporal, now)
                if alert is not None:
                    new_alerts.append(alert)

            self._seq += 1
            self._jpeg = jpeg
            self._last_seen = now
            self._frame_times.append(now)
            self._result = {
                "seq": self._seq,
                "width": width,
                "height": height,
                "inference_ms": inference_ms,
                "observations": sorted(observations, key=lambda item: -item["confidence"]),
                "new_alert_ids": [alert["id"] for alert in new_alerts],
            }
            return self.settings

    def _maybe_alert(self, temporal: TemporalObservation, now: float) -> dict[str, Any] | None:
        """Local, conservative alert rules: the fast path that never waits on a network model."""
        detection = temporal.spatial.detection
        if (
            detection.track_id is None
            or detection.label not in ALERT_LABELS
            or detection.confidence < ALERT_MIN_CONFIDENCE
        ):
            return None

        clock_position = temporal.spatial.clock_position
        name = _spoken_label(detection.label)
        behind = self.settings.mounting == "backward"
        kind: str | None = None
        priority = "info"
        if temporal.crossing_trajectory:
            kind = "crossing"
            message = f"{name} crossing {'behind you' if behind else 'ahead'}."
        elif temporal.range_trend == "approaching" and temporal.sample_count >= ALERT_MIN_SAMPLES:
            kind = "approaching"
            priority = "warn"
            message = f"{name}, {clock_position} o'clock, getting larger in view."
        elif temporal.sample_count >= ALERT_MIN_SAMPLES - 1 and detection.label == "person":
            kind = "new"
            message = f"{name} {'behind you' if behind else 'ahead'}, {clock_position} o'clock."
        if kind is None:
            return None

        key = (detection.track_id, kind)
        # A new person is announced once per track; changes may repeat after a cooldown.
        cooldown = NEW_TRACK_MEMORY_S if kind == "new" else TRACK_ALERT_COOLDOWN_S
        if now - self._alerted.get(key, float("-inf")) < cooldown:
            return None
        # Warnings may interrupt quieter notices; notices respect a global gap.
        if priority != "warn" and now - self._last_alert_at < GLOBAL_ALERT_COOLDOWN_S:
            return None

        self._alerted[key] = now
        self._last_alert_at = now
        alert = {
            "id": self._next_alert_id,
            "kind": kind,
            "priority": priority,
            "message": message,
            "track_id": detection.track_id,
            "label": detection.label,
            "clock": clock_position,
            "at": now,
        }
        self._next_alert_id += 1
        self._alerts.append(alert)
        stale = [k for k, t in self._alerted.items() if now - t > NEW_TRACK_MEMORY_S]
        for k in stale:
            del self._alerted[k]
        return alert

    # --- viewer side -----------------------------------------------------

    def update_settings(self, changes: dict[str, Any]) -> DeviceSettings:
        allowed = set(DeviceSettings.__dataclass_fields__)
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"Unknown setting(s): {', '.join(sorted(unknown))}")
        with self._lock:
            updated = replace(self.settings, **changes).validated()
            if updated.mounting != self.settings.mounting:
                self._tracker = TemporalTracker(history_size=6, max_track_age_s=3.0)
            self.settings = updated
            return updated

    def latest_jpeg(self) -> tuple[int, bytes] | None:
        with self._lock:
            return None if self._jpeg is None else (self._seq, self._jpeg)

    def briefing_context(self, window_s: float = 30.0) -> dict[str, Any]:
        """Latest observations plus recent local alerts, for the optional scene briefing."""
        with self._lock:
            now = self._clock()
            age = None if self._last_seen is None else now - self._last_seen
            return {
                "online": age is not None and age <= ONLINE_WINDOW_S and not self.settings.paused,
                "mounting": self.settings.mounting,
                "observations": list(self._result["observations"]) if self._result else [],
                "recent_alerts": [dict(a) for a in self._alerts if now - a["at"] <= window_s],
            }

    def snapshot(self, after_alert_id: int = 0) -> dict[str, Any]:
        with self._lock:
            now = self._clock()
            age = None if self._last_seen is None else round(now - self._last_seen, 2)
            fps = None
            if len(self._frame_times) >= 2:
                span = self._frame_times[-1] - self._frame_times[0]
                if span > 0:
                    fps = round((len(self._frame_times) - 1) / span, 1)
            return {
                "online": age is not None and age <= ONLINE_WINDOW_S,
                "last_seen_s": age,
                "fps": fps,
                "settings": self.settings.as_dict(),
                "result": self._result,
                "alerts": [
                    {k: v for k, v in alert.items() if k != "at"}
                    for alert in self._alerts
                    if alert["id"] > after_alert_id
                ],
            }
