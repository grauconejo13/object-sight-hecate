from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator
from urllib.parse import urlsplit
from urllib.request import urlopen

import cv2
import numpy as np


MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class CameraConfig:
    source: int | str = 0
    width: int | None = 1280
    height: int | None = 720
    snapshot_timeout: float = 3.0


class CameraSource:
    """OpenCV video source or an ESP32 CameraWebServer /capture JPEG endpoint."""

    def __init__(self, config: CameraConfig) -> None:
        self.config = config
        self._snapshot_url = (
            config.source
            if isinstance(config.source, str)
            and urlsplit(config.source).scheme in ("http", "https")
            and urlsplit(config.source).path.rstrip("/") == "/capture"
            else None
        )
        self._capture = None

        if self._snapshot_url is not None:
            return

        self._capture = cv2.VideoCapture(config.source)
        if config.width is not None:
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.width)
        if config.height is not None:
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.height)

        if not self._capture.isOpened():
            self._capture.release()
            raise RuntimeError(f"Unable to open camera/video source: {config.source!r}")

    def frames(self) -> Iterator[np.ndarray]:
        if self._snapshot_url is not None:
            while True:
                try:
                    with urlopen(self._snapshot_url, timeout=self.config.snapshot_timeout) as response:
                        jpeg = response.read(MAX_SNAPSHOT_BYTES + 1)
                except OSError as exc:
                    raise RuntimeError(
                        f"Unable to fetch ESP32 snapshot from {self._snapshot_url!r}: {exc}"
                    ) from exc

                if not jpeg or len(jpeg) > MAX_SNAPSHOT_BYTES:
                    raise RuntimeError("ESP32 snapshot is empty or exceeds 8 MiB")
                frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    raise RuntimeError("ESP32 snapshot is not a valid JPEG image")
                yield frame
            return

        while True:
            ok, frame = self._capture.read()
            if not ok:
                break
            yield frame

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()

    def __enter__(self) -> "CameraSource":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
