import unittest

from object_sight_hecate.awareness import AwarenessEngine
from object_sight_hecate.spatial.temporal import SpatialEvent


def make_event(
    *,
    timestamp: float = 1.0,
    track_id: int | None = 1,
    confidence: float = 0.90,
    clock_position: int = 12,
    horizontal_motion: str = "steady",
    range_trend: str = "steady",
    crossing_trajectory: str | None = None,
) -> SpatialEvent:
    return SpatialEvent(
        schema_version="1.0",
        timestamp=timestamp,
        source="camera-0",
        event_type="crossing" if crossing_trajectory else "track_update",
        track_id=track_id,
        label="person",
        confidence=confidence,
        horizontal_position="ahead" if clock_position == 12 else "left",
        clock_position=clock_position,
        horizontal_motion=horizontal_motion,
        range_trend=range_trend,
        crossing_trajectory=crossing_trajectory,
        delta_x=None,
        area_change_ratio=None,
    )


class AwarenessEngineTests(unittest.TestCase):
    def test_untracked_event_is_quiet(self) -> None:
        engine = AwarenessEngine()
        result = engine.evaluate(make_event(track_id=None))
        self.assertEqual(result.action, "quiet")
        self.assertIn("untracked", result.reason_codes)

    def test_low_confidence_event_is_quiet(self) -> None:
        engine = AwarenessEngine(min_confidence=0.40)
        result = engine.evaluate(make_event(confidence=0.30))
        self.assertEqual(result.action, "quiet")
        self.assertIn("low_detection_confidence", result.reason_codes)

    def test_steady_event_is_quiet(self) -> None:
        engine = AwarenessEngine()
        result = engine.evaluate(make_event())
        self.assertEqual(result.action, "quiet")
        self.assertIsNone(result.message)

    def test_lateral_motion_is_watch(self) -> None:
        engine = AwarenessEngine()
        result = engine.evaluate(make_event(horizontal_motion="moving right"))
        self.assertEqual(result.action, "watch")
        self.assertEqual(result.priority, 1)
        self.assertIn("lateral_motion", result.reason_codes)

    def test_approaching_off_axis_is_watch(self) -> None:
        engine = AwarenessEngine()
        result = engine.evaluate(make_event(range_trend="approaching", clock_position=9))
        self.assertEqual(result.action, "watch")
        self.assertIn("approaching", result.reason_codes)

    def test_high_confidence_approaching_ahead_notifies(self) -> None:
        engine = AwarenessEngine(notify_confidence=0.55)
        result = engine.evaluate(
            make_event(range_trend="approaching", confidence=0.80, clock_position=12)
        )
        self.assertEqual(result.action, "notify")
        self.assertEqual(result.priority, 2)
        self.assertEqual(result.message, "Person approaching ahead.")

    def test_crossing_notifies(self) -> None:
        engine = AwarenessEngine()
        result = engine.evaluate(make_event(crossing_trajectory="left_to_right"))
        self.assertEqual(result.action, "notify")
        self.assertIn("full_crossing", result.reason_codes)
        self.assertEqual(result.message, "Person crossing left to right.")

    def test_duplicate_notification_is_suppressed_during_cooldown(self) -> None:
        engine = AwarenessEngine(cooldown_s=2.0)
        first = engine.evaluate(make_event(timestamp=1.0, crossing_trajectory="left_to_right"))
        second = engine.evaluate(make_event(timestamp=2.0, crossing_trajectory="left_to_right"))

        self.assertEqual(first.action, "notify")
        self.assertEqual(second.action, "watch")
        self.assertTrue(second.suppressed)
        self.assertIn("cooldown", second.reason_codes)
        self.assertIsNone(second.message)

    def test_notification_can_emit_after_cooldown(self) -> None:
        engine = AwarenessEngine(cooldown_s=2.0)
        engine.evaluate(make_event(timestamp=1.0, crossing_trajectory="left_to_right"))
        result = engine.evaluate(make_event(timestamp=3.1, crossing_trajectory="left_to_right"))

        self.assertEqual(result.action, "notify")
        self.assertFalse(result.suppressed)

    def test_different_tracks_have_independent_cooldowns(self) -> None:
        engine = AwarenessEngine(cooldown_s=2.0)
        engine.evaluate(make_event(timestamp=1.0, track_id=1, crossing_trajectory="left_to_right"))
        result = engine.evaluate(
            make_event(timestamp=1.1, track_id=2, crossing_trajectory="left_to_right")
        )
        self.assertEqual(result.action, "notify")

    def test_decision_serializes(self) -> None:
        engine = AwarenessEngine()
        result = engine.evaluate(make_event(horizontal_motion="moving left"))
        payload = result.as_dict()
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["action"], "watch")
        self.assertEqual(payload["track_id"], 1)


if __name__ == "__main__":
    unittest.main()
