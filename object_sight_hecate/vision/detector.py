from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from ultralytics import YOLO


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
    """Ultralytics detector/tracker that returns model-agnostic detection records."""

    def __init__(self, model_name: str = "yolo11n.pt", confidence: float = 0.35) -> None:
        self.model = YOLO(model_name)
        self.confidence = confidence

    def track(self, frame: np.ndarray) -> list[Detection]:
        result = self.model.track(
            frame,
            persist=True,
            conf=self.confidence,
            verbose=False,
        )[0]

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
            x1, y1, x2, y2 = (int(value) for value in coords)
            detections.append(
                Detection(
                    track_id=track_id,
                    class_id=class_id,
                    label=str(names[class_id]),
                    confidence=float(confidence),
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                )
            )

        return detections
