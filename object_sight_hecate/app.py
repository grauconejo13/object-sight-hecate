from __future__ import annotations

import argparse
import time

import cv2

from object_sight_hecate.spatial.position import observe
from object_sight_hecate.vision.camera import CameraConfig, CameraSource
from object_sight_hecate.vision.detector import ObjectDetector


def _parse_source(value: str) -> int | str:
    return int(value) if value.isdigit() else value


def _require_opencv_5() -> None:
    major = int(cv2.__version__.split(".", maxsplit=1)[0])
    if major < 5:
        raise RuntimeError(
            f"Object-Sight Hecate requires OpenCV 5.x; found {cv2.__version__}. "
            "Run: pip install -r requirements.txt"
        )


def _draw_observation(frame, observation) -> None:
    detection = observation.detection
    cv2.rectangle(
        frame,
        (detection.x1, detection.y1),
        (detection.x2, detection.y2),
        (255, 255, 255),
        2,
    )

    track = "?" if detection.track_id is None else str(detection.track_id)
    text = (
        f"{detection.label} #{track} {detection.confidence:.2f} | "
        f"{observation.horizontal_position} ({observation.clock_position} o'clock)"
    )
    text_y = max(24, detection.y1 - 8)
    cv2.putText(
        frame,
        text,
        (detection.x1, text_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Object-Sight Hecate single-camera prototype")
    parser.add_argument(
        "--source",
        default="0",
        help="Camera index (for example 0) or path to a video file.",
    )
    parser.add_argument("--model", default="yolo11n.pt", help="Ultralytics model name/path.")
    parser.add_argument("--confidence", type=float, default=0.35)
    return parser


def run(source: int | str, model_name: str, confidence: float) -> None:
    _require_opencv_5()
    detector = ObjectDetector(model_name=model_name, confidence=confidence)

    previous_time = time.perf_counter()
    fps = 0.0

    try:
        with CameraSource(CameraConfig(source=source)) as camera:
            for frame in camera.frames():
                detections = detector.track(frame)
                frame_height, frame_width = frame.shape[:2]

                for detection in detections:
                    observation = observe(detection, frame_width)
                    _draw_observation(frame, observation)

                now = time.perf_counter()
                elapsed = now - previous_time
                previous_time = now
                if elapsed > 0:
                    instant_fps = 1.0 / elapsed
                    fps = instant_fps if fps == 0 else (0.9 * fps + 0.1 * instant_fps)

                cv2.putText(
                    frame,
                    f"Hecate | OpenCV {cv2.__version__} | {fps:.1f} FPS | {frame_width}x{frame_height}",
                    (16, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )
                cv2.imshow("Object-Sight Hecate", frame)

                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    break
    finally:
        cv2.destroyAllWindows()


def main() -> None:
    args = build_parser().parse_args()
    run(
        source=_parse_source(args.source),
        model_name=args.model,
        confidence=args.confidence,
    )
