from __future__ import annotations

from dataclasses import dataclass

import numpy as np


# Classes a pedestrian almost never meets, which the small model often hallucinates
# (shelf rows as a "train", fridges as a "boat"). Kept only when very confident.
UNLIKELY_LABELS = frozenset({
    "train", "airplane", "boat", "elephant", "bear", "zebra", "giraffe",
    "surfboard", "skis", "snowboard", "kite", "frisbee", "toilet",
})
UNLIKELY_MIN_CONFIDENCE = 0.75


def is_plausible(label: str, confidence: float) -> bool:
    return label not in UNLIKELY_LABELS or confidence >= UNLIKELY_MIN_CONFIDENCE


@dataclass(frozen=True)
class Detection:
    track_id: int | None
    class_id: int
    label: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def center(self) -> tuple[int, int]:
        return ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)


class ObjectDetector:
    """Ultralytics detector/tracker returning model-agnostic detection records."""

    def __init__(self, model_name: str = "yolo11n.pt", confidence: float = 0.35) -> None:
        # Imported lazily so spatial utilities, the API, and tests load without PyTorch.
        from ultralytics import YOLO

        self.model = YOLO(model_name)
        self.confidence = confidence

    def track(self, frame: np.ndarray) -> list[Detection]:
        result = self.model.track(
            frame,
            persist=True,
            conf=self.confidence,
            verbose=False,
        )[0]
        return self._detections(result)

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """Stateless inference for independent browser uploads."""
        result = self.model.predict(
            frame,
            conf=self.confidence,
            verbose=False,
        )[0]
        return self._detections(result)

    @staticmethod
    def _detections(result) -> list[Detection]:
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return []

        xyxy = boxes.xyxy.cpu().numpy()
        class_ids = boxes.cls.int().cpu().tolist()
        confidences = boxes.conf.cpu().tolist()
        track_ids = (
            boxes.id.int().cpu().tolist()
            if boxes.id is not None
            else [None] * len(class_ids)
        )

        names = result.names
        detections: list[Detection] = []
        for coords, class_id, confidence, track_id in zip(
            xyxy, class_ids, confidences, track_ids, strict=True
        ):
            label = str(names[class_id])
            if not is_plausible(label, float(confidence)):
                continue
            x1, y1, x2, y2 = (int(value) for value in coords)
            detections.append(
                Detection(
                    track_id=track_id,
                    class_id=class_id,
                    label=label,
                    confidence=float(confidence),
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                )
            )

        return detections
