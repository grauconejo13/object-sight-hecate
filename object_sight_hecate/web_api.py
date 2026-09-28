"""Stateless frame analysis API for an opt-in phone-camera field test."""

from __future__ import annotations

import os
import time
from functools import lru_cache
from threading import Lock

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from object_sight_hecate.spatial.position import observe
from object_sight_hecate.vision.detector import ObjectDetector

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
_model_lock = Lock()

app = FastAPI(title="Hecate Field Test", version="0.1.0")
allowed_origins = [
    "http://localhost:5173",
    *[origin.strip().rstrip("/") for origin in os.getenv("FRONTEND_ORIGINS", "").split(",") if origin.strip()],
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@lru_cache(maxsize=1)
def get_detector() -> ObjectDetector:
    return ObjectDetector(model_name=os.getenv("HECATE_MODEL", "yolo11n.pt"))


def analyze_jpeg(jpeg: bytes) -> dict:
    frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Image must be a valid JPEG")
    height, width = frame.shape[:2]
    if width * height > 3_000_000:
        raise ValueError("Image dimensions exceed the 3 megapixel limit")

    start = time.perf_counter()
    with _model_lock:
        detections = get_detector().detect(frame)
    observations = []
    for detection in detections:
        spatial = observe(detection, width)
        observations.append({
            "label": detection.label,
            "confidence": round(detection.confidence, 3),
            "box": [detection.x1, detection.y1, detection.x2, detection.y2],
            "position": spatial.horizontal_position,
            "clock": spatial.clock_position,
        })
    return {
        "width": width,
        "height": height,
        "inference_ms": round((time.perf_counter() - start) * 1000),
        "observations": observations,
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/v1/analyze")
async def analyze(request: Request) -> dict:
    if request.headers.get("content-type", "").split(";")[0].strip() != "image/jpeg":
        raise HTTPException(status_code=415, detail="Send a JPEG with Content-Type: image/jpeg")

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="JPEG exceeds 2 MiB")
    if not body:
        raise HTTPException(status_code=400, detail="Empty image")

    try:
        return await run_in_threadpool(analyze_jpeg, bytes(body))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
