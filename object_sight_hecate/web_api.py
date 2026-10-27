"""Field-test API: phone-camera frame analysis and the wearable ESP32 camera.

Route groups:
- /v1/analyze      phone browser uploads one frame (tailnet-only).
- /v1/device/*     the ESP32 pushes frames; token-protected. This is the ONLY
                   prefix that should be exposed publicly (Tailscale Funnel).
- /v1/esp32/*      the phone app views the ESP32 feed and edits its settings
                   (tailnet-only, like /v1/analyze).
"""

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

from object_sight_hecate.device import DeviceSession

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
    allow_methods=["GET", "POST", "PUT"],
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


@lru_cache(maxsize=1)
def get_device_session() -> DeviceSession:
    # A separate model instance: persistent tracking state must not mix with
    # the stateless phone uploads served by get_detector().
    return DeviceSession(
        lambda: ObjectDetector(model_name=os.getenv("HECATE_MODEL", "yolo11n.pt"))
    )


async def read_jpeg_body(request: Request, limit: int = MAX_UPLOAD_BYTES) -> bytes:
    if request.headers.get("content-type", "").split(";")[0].strip() != "image/jpeg":
        raise HTTPException(status_code=415, detail="Send a JPEG with Content-Type: image/jpeg")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise HTTPException(status_code=413, detail="JPEG exceeds 2 MiB")
    if not body:
        raise HTTPException(status_code=400, detail="Empty image")
    return bytes(body)


def require_device_token(request: Request) -> None:
    expected = os.getenv("HECATE_DEVICE_TOKEN", "")
    if len(expected) < 16:
        raise HTTPException(status_code=503, detail="Device ingest is disabled: set HECATE_DEVICE_TOKEN (16+ chars)")
    supplied = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Invalid device token")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/v1/analyze")
async def analyze(request: Request) -> dict:
    body = await read_jpeg_body(request)
    try:
        return await run_in_threadpool(analyze_jpeg, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# --- ESP32 device (public via Funnel, token required) -------------------

@app.post("/v1/device/frame")
async def device_frame(request: Request, response: Response) -> dict:
    require_device_token(request)
    body = await read_jpeg_body(request)
    session = get_device_session()
    try:
        settings = await run_in_threadpool(session.ingest, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    response.headers.update(settings.as_headers())
    return {"ok": True, "settings": settings.as_dict()}


@app.get("/v1/device/settings")
def device_settings(request: Request, response: Response) -> dict:
    """Heartbeat while paused: the ESP32 learns when to resume without sending frames."""
    require_device_token(request)
    settings = get_device_session().heartbeat()
    response.headers.update(settings.as_headers())
    return {"ok": True, "settings": settings.as_dict()}


# --- ESP32 viewer (phone app over the tailnet) ---------------------------

@app.get("/v1/esp32/latest")
def esp32_latest(after_alert: int = 0) -> dict:
    return get_device_session().snapshot(after_alert_id=after_alert)


@app.get("/v1/esp32/frame.jpg")
def esp32_frame(seq: int | None = None) -> Response:
    """Serve the exact frame whose detections the phone just received."""
    latest = get_device_session().latest_jpeg()
    if latest is None:
        raise HTTPException(status_code=404, detail="No ESP32 frame received yet")
    latest_seq, jpeg = latest
    if seq is not None and seq != latest_seq:
        raise HTTPException(
            status_code=409,
            detail="Requested frame is no longer current; fetch a fresh snapshot",
        )
    return Response(
        content=jpeg,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store", "X-Hecate-Seq": str(latest_seq)},
    )


@app.put("/v1/esp32/settings")
async def esp32_update_settings(request: Request) -> dict:
    try:
        changes = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Send settings as a JSON object") from exc
    if not isinstance(changes, dict):
        raise HTTPException(status_code=400, detail="Send settings as a JSON object")
    try:
        settings = get_device_session().update_settings(changes)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"settings": settings.as_dict()}
