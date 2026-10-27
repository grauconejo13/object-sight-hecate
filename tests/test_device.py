import os
import unittest

import cv2
import numpy as np

from object_sight_hecate.device import DeviceSession, DeviceSettings, wearer_direction
from object_sight_hecate.vision.detector import Detection


def jpeg(width: int = 640, height: int = 480) -> bytes:
    ok, buffer = cv2.imencode(".jpg", np.zeros((height, width, 3), dtype=np.uint8))
    assert ok
    return buffer.tobytes()


def person(track_id: int, center_x: int, size: int = 100, label: str = "person", confidence: float = 0.9) -> Detection:
    half = size // 2
    return Detection(track_id, 0, label, confidence, center_x - half, 240 - half, center_x + half, 240 + half)


class ScriptedTracker:
    def __init__(self, frames: list[list[Detection]]) -> None:
        self.frames = list(frames)

    def track(self, frame):
        return self.frames.pop(0) if self.frames else []


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def session_with(frames, clock=None) -> DeviceSession:
    return DeviceSession(lambda: ScriptedTracker(frames), clock=clock or Clock())


class WearerDirectionTests(unittest.TestCase):
    def test_backward_camera_mirrors_sides_behind_the_wearer(self) -> None:
        self.assertEqual(wearer_direction(0.1, "backward"), ("behind right", 5))
        self.assertEqual(wearer_direction(0.5, "backward"), ("behind", 6))
        self.assertEqual(wearer_direction(0.9, "backward"), ("behind left", 7))

    def test_forward_camera_keeps_existing_mapping(self) -> None:
        self.assertEqual(wearer_direction(0.1, "forward"), ("left", 9))
        self.assertEqual(wearer_direction(0.5, "forward"), ("ahead", 12))
        self.assertEqual(wearer_direction(0.9, "forward"), ("right", 3))


class DeviceSettingsTests(unittest.TestCase):
    def test_rejects_invalid_values(self) -> None:
        for bad in ({"frame_size": "UXGA"}, {"jpeg_quality": 4}, {"interval_ms": 333}, {"mounting": "up"}):
            with self.assertRaises(ValueError):
                session_with([]).update_settings(bad)

    def test_rejects_unknown_keys(self) -> None:
        with self.assertRaises(ValueError):
            session_with([]).update_settings({"wifi_password": "x"})

    def test_headers_are_compact_strings(self) -> None:
        headers = DeviceSettings(paused=True, vflip=True).as_headers()
        self.assertEqual(headers["X-Hecate-Paused"], "1")
        self.assertEqual(headers["X-Hecate-Vflip"], "1")
        self.assertEqual(headers["X-Hecate-Frame-Size"], "VGA")


class DeviceSessionTests(unittest.TestCase):
    def test_offline_until_first_frame_then_online(self) -> None:
        clock = Clock()
        session = session_with([[]], clock)
        self.assertFalse(session.snapshot()["online"])
        session.ingest(jpeg())
        snap = session.snapshot()
        self.assertTrue(snap["online"])
        self.assertEqual(snap["result"]["seq"], 1)
        clock.now += 10
        self.assertFalse(session.snapshot()["online"])

    def test_invalid_jpeg_is_rejected_without_replacing_the_last_frame(self) -> None:
        session = session_with([[]])
        session.ingest(jpeg())
        with self.assertRaises(ValueError):
            session.ingest(b"not a jpeg")
        self.assertEqual(session.latest_jpeg()[0], 1)

    def test_observations_use_rear_mounting_clock(self) -> None:
        session = session_with([[person(1, 60)]])
        session.ingest(jpeg())
        item = session.snapshot()["result"]["observations"][0]
        self.assertEqual((item["position"], item["clock"]), ("behind right", 5))
        self.assertEqual(item["event"]["clock_position"], 5)

    def test_new_person_announced_once_after_track_settles(self) -> None:
        clock = Clock()
        session = session_with([[person(1, 320)]] * 8, clock)
        for _ in range(8):
            session.ingest(jpeg())
            clock.now += 0.4
        alerts = session.snapshot()["alerts"]
        self.assertEqual([a["kind"] for a in alerts], ["new"])
        self.assertEqual(alerts[0]["message"], "Person behind you, 6 o'clock.")

    def test_growing_box_raises_a_warning_and_respects_cooldown(self) -> None:
        clock = Clock()
        frames = [[person(1, 320, size=60 + 15 * i)] for i in range(12)]
        session = session_with(frames, clock)
        for _ in range(12):
            session.ingest(jpeg())
            clock.now += 0.4
        kinds = [a["kind"] for a in session.snapshot()["alerts"]]
        self.assertEqual(kinds.count("approaching"), 1)
        warn = next(a for a in session.snapshot()["alerts"] if a["kind"] == "approaching")
        self.assertEqual(warn["priority"], "warn")
        self.assertEqual(warn["message"], "Person, 6 o'clock, getting larger in view.")

    def test_irrelevant_and_low_confidence_objects_stay_silent(self) -> None:
        clock = Clock()
        frames = [[person(1, 320, label="chair"), person(2, 100, confidence=0.4)]] * 6
        session = session_with(frames, clock)
        for _ in range(6):
            session.ingest(jpeg())
            clock.now += 0.4
        self.assertEqual(session.snapshot()["alerts"], [])

    def test_after_alert_filters_already_spoken_alerts(self) -> None:
        clock = Clock()
        session = session_with([[person(1, 320)]] * 4, clock)
        for _ in range(4):
            session.ingest(jpeg())
            clock.now += 0.4
        first = session.snapshot()["alerts"][0]["id"]
        self.assertEqual(session.snapshot(after_alert_id=first)["alerts"], [])

    def test_changing_mounting_resets_track_history(self) -> None:
        session = session_with([[person(1, 320)]] * 3)
        session.ingest(jpeg())
        session.ingest(jpeg())
        session.update_settings({"mounting": "forward"})
        session.ingest(jpeg())
        item = session.snapshot()["result"]["observations"][0]
        self.assertEqual(item["samples"], 1)
        self.assertEqual(item["clock"], 12)


try:
    from fastapi.testclient import TestClient
except ImportError:  # FastAPI is only installed for the web field test.
    TestClient = None


@unittest.skipIf(TestClient is None, "fastapi not installed")
class DeviceApiTests(unittest.TestCase):
    TOKEN = "test-token-0123456789"

    def setUp(self) -> None:
        from object_sight_hecate import web_api

        self.web_api = web_api
        self.session = session_with([[person(1, 320)]] * 10)
        self._original = web_api.get_device_session
        web_api.get_device_session = lambda: self.session
        os.environ["HECATE_DEVICE_TOKEN"] = self.TOKEN
        self.client = TestClient(web_api.app)

    def tearDown(self) -> None:
        self.web_api.get_device_session = self._original
        os.environ.pop("HECATE_DEVICE_TOKEN", None)

    def post_frame(self, token: str | None = TOKEN):
        headers = {"Content-Type": "image/jpeg"}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        return self.client.post("/v1/device/frame", content=jpeg(), headers=headers)

    def test_frame_requires_token(self) -> None:
        self.assertEqual(self.post_frame(token=None).status_code, 401)
        self.assertEqual(self.post_frame(token="wrong-token-0123456789").status_code, 401)

    def test_ingest_disabled_without_configured_token(self) -> None:
        os.environ["HECATE_DEVICE_TOKEN"] = "short"
        self.assertEqual(self.post_frame().status_code, 503)

    def test_frame_returns_settings_headers_and_viewer_sees_it(self) -> None:
        response = self.post_frame()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Hecate-Frame-Size"], "VGA")
        latest = self.client.get("/v1/esp32/latest").json()
        self.assertTrue(latest["online"])
        frame = self.client.get("/v1/esp32/frame.jpg")
        self.assertEqual(frame.headers["content-type"], "image/jpeg")
        self.assertEqual(frame.headers["cache-control"], "no-store")
        self.assertEqual(frame.headers["X-Hecate-Seq"], "1")
        self.assertEqual(self.client.get("/v1/esp32/frame.jpg?seq=1").status_code, 200)
        self.assertEqual(self.client.get("/v1/esp32/frame.jpg?seq=2").status_code, 409)

    def test_phone_settings_reach_the_device(self) -> None:
        put = self.client.put("/v1/esp32/settings", json={"paused": True, "frame_size": "SVGA"})
        self.assertEqual(put.status_code, 200)
        heartbeat = self.client.get("/v1/device/settings", headers={"Authorization": f"Bearer {self.TOKEN}"})
        self.assertEqual(heartbeat.headers["X-Hecate-Paused"], "1")
        self.assertEqual(heartbeat.headers["X-Hecate-Frame-Size"], "SVGA")

    def test_bad_settings_are_rejected(self) -> None:
        self.assertEqual(self.client.put("/v1/esp32/settings", json={"interval_ms": 5}).status_code, 400)
        self.assertEqual(self.client.put("/v1/esp32/settings", json=["nope"]).status_code, 400)

    def test_frame_before_any_upload_is_404(self) -> None:
        self.assertEqual(self.client.get("/v1/esp32/frame.jpg").status_code, 404)


if __name__ == "__main__":
    unittest.main()
