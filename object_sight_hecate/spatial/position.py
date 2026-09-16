from __future__ import annotations

from dataclasses import dataclass

from object_sight_hecate.vision.detector import Detection


@dataclass(frozen=True)
class SpatialObservation:
    detection: Detection
    horizontal_position: str
    clock_position: int
    normalized_x: float


def horizontal_position(normalized_x: float) -> tuple[str, int]:
    """Map image-space x position to a simple wearer-relative direction hint."""
    if normalized_x < 1 / 3:
        return "left", 9
    if normalized_x > 2 / 3:
        return "right", 3
    return "ahead", 12


def observe(detection: Detection, frame_width: int) -> SpatialObservation:
    if frame_width <= 0:
        raise ValueError("frame_width must be positive")

    center_x, _ = detection.center
    normalized_x = min(max(center_x / frame_width, 0.0), 1.0)
    label, clock = horizontal_position(normalized_x)

    return SpatialObservation(
        detection=detection,
        horizontal_position=label,
        clock_position=clock,
        normalized_x=normalized_x,
    )
