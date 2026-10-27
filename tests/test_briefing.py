import json
import os
import unittest

from object_sight_hecate.briefing import (
    Briefer,
    SceneFacts,
    build_facts,
    check_briefing,
    clean_reply,
    local_briefing,
)

PERSON = {"label": "person", "confidence": 0.9, "clock": 6, "range_trend": "steady"}
CAR = {"label": "car", "confidence": 0.8, "clock": 7, "range_trend": "approaching"}


def reply(content: str, status: int = 200):
    body = json.dumps({"choices": [{"message": {"role": "assistant", "content": content}}]}).encode()
    calls = []

    def transport(url, headers, payload, timeout):
        calls.append({"url": url, "headers": headers, "body": json.loads(payload)})
        return status, body

    return transport, calls


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class FactsTests(unittest.TestCase):
    def test_drops_low_confidence_and_bad_rows_and_orders_people_first(self) -> None:
        facts = build_facts(
            [{"label": "chair", "confidence": 0.95, "clock": 5}, CAR, PERSON,
             {"label": "dog", "confidence": 0.2, "clock": 6}, {"label": "person"}],
            view="backward",
        )
        self.assertEqual([o["label"] for o in facts.objects], ["person", "car", "chair"])
        self.assertEqual(facts.objects[1]["size_trend"], "larger in view")
        self.assertEqual(facts.view_name, "Rear view")

    def test_prompt_never_contains_boxes_or_images(self) -> None:
        facts = build_facts([{**PERSON, "box": [1, 2, 3, 4], "track_id": 9}], view="backward")
        prompt = facts.as_prompt_json()
        self.assertNotIn("box", prompt)
        self.assertNotIn("track_id", prompt)

    def test_recent_alerts_become_neutral_changes(self) -> None:
        facts = build_facts([PERSON], view="backward", recent_alerts=[
            {"kind": "approaching", "label": "person", "clock": 6},
            {"kind": "crossing", "label": "bicycle", "clock": 7},
        ])
        self.assertEqual(facts.recent_changes, ("person at 6 o'clock grew larger in view", "bicycle crossed the view"))


class LocalBriefingTests(unittest.TestCase):
    def test_example_sentence(self) -> None:
        facts = build_facts([PERSON, {**CAR, "clock": 3}], view="backward")
        self.assertEqual(local_briefing(facts), "Rear view: a person at 6 o'clock and a car at 3 o'clock.")

    def test_groups_repeats_keeping_priority_order(self) -> None:
        facts = build_facts([{"label": "chair", "confidence": 0.9, "clock": 5}] * 3 + [PERSON, PERSON], view="phone")
        self.assertEqual(local_briefing(facts), "Camera view: two people at 6 o'clock and three chairs at 5 o'clock.")

    def test_empty_and_stale(self) -> None:
        self.assertEqual(local_briefing(build_facts([], view="forward")), "Front view: nothing detected.")
        self.assertIn("no current frame", local_briefing(build_facts([PERSON], view="backward", stale=True)))


class GuardTests(unittest.TestCase):
    facts = build_facts([PERSON, CAR], view="backward")

    def test_accepts_cautious_sentence(self) -> None:
        self.assertIsNone(check_briefing("Rear view: a person at 6 o'clock and a car at 7 o'clock, larger in view.", self.facts))

    def test_rejects_danger_intent_identity_and_distance(self) -> None:
        for text in (
            "Rear view: a suspicious person at 6 o'clock.",
            "Rear view: a person at 6 o'clock is following you.",
            "Rear view: a man at 6 o'clock.",
            "Rear view: a car approaching at 7 o'clock.",
            "Rear view: a person 3 m behind you at 6 o'clock.",
            "Rear view: a car close behind at 7 o'clock.",
        ):
            with self.subTest(text=text):
                self.assertIsNotNone(check_briefing(text, self.facts))

    def test_rejects_directions_not_in_facts(self) -> None:
        self.assertIn("4 o'clock", check_briefing("Rear view: a person at 4 o'clock.", self.facts))

    def test_strips_reasoning_and_quotes(self) -> None:
        self.assertEqual(clean_reply('<think>count them</think>\n"Rear view: a person at 6 o\'clock."'), "Rear view: a person at 6 o'clock.")
        self.assertEqual(clean_reply("planning...</think> Rear view: a car at 7 o'clock."), "Rear view: a car at 7 o'clock.")


class BrieferTests(unittest.TestCase):
    facts = build_facts([PERSON, CAR], view="backward")

    def test_without_key_uses_local_and_says_nebius_unavailable(self) -> None:
        result = Briefer(api_key=None).brief(self.facts)
        self.assertEqual(result["provider"], "local")
        self.assertEqual(result["nebius"], "unavailable")
        self.assertIn("NEBIUS_API_KEY", result["reason"])

    def test_calls_token_factory_with_nemotron_and_bearer_key(self) -> None:
        transport, calls = reply("Rear view: a person at 6 o'clock and a car at 7 o'clock.")
        result = Briefer(api_key="sk-test", transport=transport).brief(self.facts)
        self.assertEqual(result["provider"], "nemotron")
        self.assertEqual(result["text"], "Rear view: a person at 6 o'clock and a car at 7 o'clock.")
        call = calls[0]
        self.assertEqual(call["url"], "https://api.tokenfactory.nebius.com/v1/chat/completions")
        self.assertEqual(call["headers"]["Authorization"], "Bearer sk-test")
        self.assertEqual(call["body"]["model"], "nvidia/nemotron-3-super-120b-a12b")
        self.assertEqual(json.loads(call["body"]["messages"][1]["content"])["view_name"], "Rear view")

    def test_guarded_reply_falls_back_to_local(self) -> None:
        transport, _ = reply("Rear view: a dangerous man at 6 o'clock.")
        result = Briefer(api_key="sk-test", transport=transport).brief(self.facts)
        self.assertEqual(result["provider"], "local")
        self.assertEqual(result["nebius"], "guarded")
        self.assertEqual(result["text"], "Rear view: a person at 6 o'clock and a car at 7 o'clock.")

    def test_http_errors_and_network_failures_fall_back(self) -> None:
        for status, nebius in ((401, "unavailable"), (429, "error"), (503, "error")):
            transport, _ = reply("", status=status)
            result = Briefer(api_key="sk-test", transport=transport).brief(self.facts)
            self.assertEqual((result["provider"], result["nebius"]), ("local", nebius))

        def down(*_):
            raise TimeoutError()

        result = Briefer(api_key="sk-test", transport=down).brief(self.facts)
        self.assertEqual(result["provider"], "local")
        self.assertIn("unreachable", result["reason"])

    def test_same_scene_is_cached_briefly(self) -> None:
        clock = Clock()
        transport, calls = reply("Rear view: a person at 6 o'clock and a car at 7 o'clock.")
        briefer = Briefer(api_key="sk-test", transport=transport, clock=clock)
        briefer.brief(self.facts)
        self.assertTrue(briefer.brief(self.facts)["cached"])
        clock.now += 11
        briefer.brief(self.facts)
        self.assertEqual(len(calls), 2)

    def test_stale_camera_skips_the_cloud_call(self) -> None:
        transport, calls = reply("anything")
        stale = build_facts([PERSON], view="backward", stale=True)
        result = Briefer(api_key="sk-test", transport=transport).brief(stale)
        self.assertEqual(calls, [])
        self.assertEqual(result["provider"], "local")

    def test_status_never_exposes_the_key(self) -> None:
        status = Briefer(api_key="sk-secret").status()
        self.assertTrue(status["available"])
        self.assertNotIn("sk-secret", json.dumps(status))

    def test_from_env(self) -> None:
        os.environ["NEBIUS_API_KEY"] = "sk-env"
        os.environ["NEBIUS_BASE_URL"] = "https://example.test/v1/"
        try:
            briefer = Briefer.from_env()
        finally:
            os.environ.pop("NEBIUS_API_KEY")
            os.environ.pop("NEBIUS_BASE_URL")
        self.assertTrue(briefer.available)
        self.assertEqual(briefer.base_url, "https://example.test/v1")


try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None


@unittest.skipIf(TestClient is None, "fastapi not installed")
class BriefingApiTests(unittest.TestCase):
    def setUp(self) -> None:
        from object_sight_hecate import web_api
        from test_device import Clock as DeviceClock, jpeg, person, session_with

        self.web_api = web_api
        self.clock = DeviceClock()
        self.session = session_with([[person(1, 320)]] * 5, self.clock)
        self.transport, self.calls = reply("Rear view: a person at 6 o'clock.")
        self.originals = (web_api.get_device_session, web_api.get_briefer)
        web_api.get_device_session = lambda: self.session
        briefer = Briefer(api_key="sk-test", transport=self.transport)
        web_api.get_briefer = lambda: briefer
        self.jpeg = jpeg
        self.client = TestClient(web_api.app)

    def tearDown(self) -> None:
        self.web_api.get_device_session, self.web_api.get_briefer = self.originals

    def test_esp32_briefing_uses_latest_tracked_frame(self) -> None:
        self.session.ingest(self.jpeg())
        data = self.client.post("/v1/briefing", json={"source": "esp32"}).json()
        self.assertEqual((data["provider"], data["text"]), ("nemotron", "Rear view: a person at 6 o'clock."))
        sent = json.loads(self.calls[0]["body"]["messages"][1]["content"])
        self.assertEqual(sent["objects"][0]["clock"], 6)

    def test_esp32_offline_answers_locally(self) -> None:
        data = self.client.post("/v1/briefing", json={"source": "esp32"}).json()
        self.assertEqual(data["provider"], "local")
        self.assertEqual(self.calls, [])

    def test_phone_briefing_uses_supplied_observations(self) -> None:
        self.transport, self.calls = reply("Camera view: a person at 12 o'clock.")
        self.web_api.get_briefer = lambda: Briefer(api_key="sk-test", transport=self.transport)
        data = self.client.post("/v1/briefing", json={"source": "phone", "observations": [
            {"label": "person", "confidence": 0.9, "clock": 12, "position": "ahead"}]}).json()
        self.assertEqual(data["text"], "Camera view: a person at 12 o'clock.")

    def test_bad_requests(self) -> None:
        self.assertEqual(self.client.post("/v1/briefing", json={"source": "drone"}).status_code, 400)
        self.assertEqual(self.client.post("/v1/briefing", json={"source": "phone", "observations": "x"}).status_code, 400)

    def test_status_endpoint(self) -> None:
        self.assertTrue(self.client.get("/v1/briefing/status").json()["available"])


if __name__ == "__main__":
    unittest.main()
