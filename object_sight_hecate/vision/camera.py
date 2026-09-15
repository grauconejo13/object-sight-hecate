from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import cv2
import numpy as np


@dataclass(frozen=True)
class CameraConfig:
    source: int | str = 0
    width: int | None = 1280
    height: int | None = 720


class CameraSource:
    """Small OpenCV-backed frame source for the first Hecate prototype."""

    def __init__(self, config: CameraConfig) -> None:
        self.config = config
        self._capture = cv2.VideoCapture(config.source)

        if config.width is not None:
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.width)
        if config.height is not None:
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.height)

        if not self._capture.isOpened():
            raise RuntimeError(f"Unable to open camera/video source: {config.source!r}")

    def frames(self) -> Iterator[np.ndarray]:
        while True:
            ok, frame = self._capture.read()
            if not ok:
                break
            yield frame

    def close(self) -> None:
        self._capture.release()

    def __enter__(self) -> "CameraSource":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
