"""Stateless frame analysis API for opt-in phone and ESP32 camera field tests."""

from __future__ import annotations

import hmac
import os
import time
from functools import lru_cache
from threading import Lock

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from object_sight_hecate.spatial.position import observe
from object_sight_hecate.vision.detector import ObjectDetector

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_DEVICE_ID_LENGTH = 64
_model_lock = Lock()
_device_frame_lock = Lock()
_latest_device_frames: dict[str, dict] = {}

app = FastAPI(title="Hecate Field Test", version="0.2.0")
allowed_origins = [
    "http://localhost:5173",
    *[origin.strip().rstrip("/") for origin in os.getenv("FRONTEND_ORIGINS", "").split(",") if origin.strip()],
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Hecate-Device-Token"],
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


async def read_jpeg(request: Request) -> bytes:
    if request.headers.get("content-type", "").split(";")[0].strip() != "image/jpeg":
        raise HTTPException(status_code=415, detail="Send a JPEG with Content-Type: image/jpeg")

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="JPEG exceeds 2 MiB")
    if not body:
        raise HTTPException(status_code=400, detail="Empty image")
    return bytes(body)


def validate_device_id(device_id: str) -> None:
    if not device_id or len(device_id) > MAX_DEVICE_ID_LENGTH or not all(
        character.isalnum() or character in "-_" for character in device_id
    ):
        raise HTTPException(status_code=400, detail="Invalid device id")


def require_device_token(request: Request) -> None:
    expected = os.getenv("HECATE_DEVICE_TOKEN")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="ESP32 upload is not configured. Set HECATE_DEVICE_TOKEN on the backend.",
        )
    received = request.headers.get("X-Hecate-Device-Token", "")
    if not received or not hmac.compare_digest(received, expected):
        raise HTTPException(status_code=401, detail="Invalid device token")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/v1/analyze")
async def analyze(request: Request) -> dict:
    jpeg = await read_jpeg(request)
    try:
        return await run_in_threadpool(analyze_jpeg, jpeg)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/devices/{device_id}/frames")
async def ingest_device_frame(device_id: str, request: Request) -> dict:
    """Accept one ESP32 JPEG and retain only its latest in-memory field-test result."""

    validate_device_id(device_id)
    require_device_token(request)
    jpeg = await read_jpeg(request)
    try:
        result = await run_in_threadpool(analyze_jpeg, jpeg)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    received_at = time.time()
    with _device_frame_lock:
        _latest_device_frames[device_id] = {
            "jpeg": jpeg,
            "received_at": received_at,
            "result": result,
        }
    return {
        "device_id": device_id,
        "received_at": received_at,
        "result": result,
    }


@app.get("/v1/devices/{device_id}/latest")
def latest_device_result(device_id: str) -> dict:
    """Return the latest transient analysis result for a local, Tailscale-protected test."""

    validate_device_id(device_id)
    with _device_frame_lock:
        latest = _latest_device_frames.get(device_id)
        if latest is None:
            raise HTTPException(status_code=404, detail="No frame received from this device yet")
        result = latest["result"]
        received_at = latest["received_at"]

    return {
        "device_id": device_id,
        "received_at": received_at,
        "age_ms": round((time.time() - received_at) * 1000),
        "result": result,
    }


@app.get("/v1/devices/{device_id}/latest.jpg")
def latest_device_frame(device_id: str) -> Response:
    """Return the latest transient JPEG. Do not expose this local-test route publicly."""

    validate_device_id(device_id)
    with _device_frame_lock:
        latest = _latest_device_frames.get(device_id)
        if latest is None:
            raise HTTPException(status_code=404, detail="No frame received from this device yet")
        jpeg = latest["jpeg"]

    return Response(
        content=jpeg,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )
