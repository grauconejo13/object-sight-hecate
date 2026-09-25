import unittest

from object_sight_hecate.spatial.position import observe
from object_sight_hecate.spatial.temporal import TemporalTracker
from object_sight_hecate.vision.detector import Detection


FRAME_WIDTH = 1000
FRAME_HEIGHT = 500


def make_detection(
    track_id: int | None,
    center_x: int,
    width: int = 100,
    height: int = 100,
) -> Detection:
    half_w = width // 2
    half_h = height // 2
    return Detection(
        track_id=track_id,
        class_id=0,
        label="person",
        confidence=0.9,
        x1=center_x - half_w,
        y1=250 - half_h,
        x2=center_x + half_w,
        y2=250 + half_h,
    )


class TemporalTrackerTests(unittest.TestCase):
    def test_first_sample_has_unknown_motion(self) -> None:
        tracker = TemporalTracker()
        result = tracker.update(
            observe(make_detection(1, 500), FRAME_WIDTH),
            FRAME_WIDTH,
            FRAME_HEIGHT,
            timestamp=0.0,
        )
        self.assertEqual(result.horizontal_motion, "unknown")
        self.assertEqual(result.range_trend, "unknown")
        self.assertIsNone(result.crossing_trajectory)

    def test_untracked_detection_stays_unknown(self) -> None:
        tracker = TemporalTracker()
        result = tracker.update(
            observe(make_detection(None, 500), FRAME_WIDTH),
            FRAME_WIDTH,
            FRAME_HEIGHT,
            timestamp=0.0,
        )
        self.assertEqual(result.sample_count, 0)
        self.assertEqual(result.horizontal_motion, "unknown")

    def test_detects_rightward_motion(self) -> None:
        tracker = TemporalTracker(horizontal_threshold=0.03)
        tracker.update(observe(make_detection(1, 400), FRAME_WIDTH), FRAME_WIDTH, FRAME_HEIGHT, 0.0)
        result = tracker.update(
            observe(make_detection(1, 460), FRAME_WIDTH),
            FRAME_WIDTH,
            FRAME_HEIGHT,
            timestamp=0.1,
        )
        self.assertEqual(result.horizontal_motion, "moving right")

    def test_detects_leftward_motion(self) -> None:
        tracker = TemporalTracker(horizontal_threshold=0.03)
        tracker.update(observe(make_detection(1, 600), FRAME_WIDTH), FRAME_WIDTH, FRAME_HEIGHT, 0.0)
        result = tracker.update(
            observe(make_detection(1, 540), FRAME_WIDTH),
            FRAME_WIDTH,
            FRAME_HEIGHT,
            timestamp=0.1,
        )
        self.assertEqual(result.horizontal_motion, "moving left")

    def test_small_horizontal_change_is_steady(self) -> None:
        tracker = TemporalTracker(horizontal_threshold=0.03)
        tracker.update(observe(make_detection(1, 500), FRAME_WIDTH), FRAME_WIDTH, FRAME_HEIGHT, 0.0)
        result = tracker.update(
            observe(make_detection(1, 515), FRAME_WIDTH),
            FRAME_WIDTH,
            FRAME_HEIGHT,
            timestamp=0.1,
        )
        self.assertEqual(result.horizontal_motion, "steady")

    def test_growing_box_is_approaching(self) -> None:
        tracker = TemporalTracker(area_change_threshold=0.10)
        tracker.update(
            observe(make_detection(1, 500, width=100, height=100), FRAME_WIDTH),
            FRAME_WIDTH,
            FRAME_HEIGHT,
            timestamp=0.0,
        )
        result = tracker.update(
            observe(make_detection(1, 500, width=120, height=120), FRAME_WIDTH),
            FRAME_WIDTH,
            FRAME_HEIGHT,
            timestamp=0.1,
        )
        self.assertEqual(result.range_trend, "approaching")

    def test_shrinking_box_is_receding(self) -> None:
        tracker = TemporalTracker(area_change_threshold=0.10)
        tracker.update(
            observe(make_detection(1, 500, width=120, height=120), FRAME_WIDTH),
            FRAME_WIDTH,
            FRAME_HEIGHT,
            timestamp=0.0,
        )
        result = tracker.update(
            observe(make_detection(1, 500, width=100, height=100), FRAME_WIDTH),
            FRAME_WIDTH,
            FRAME_HEIGHT,
            timestamp=0.1,
        )
        self.assertEqual(result.range_trend, "receding")

    def test_track_histories_are_isolated(self) -> None:
        tracker = TemporalTracker(horizontal_threshold=0.03)
        tracker.update(observe(make_detection(1, 400), FRAME_WIDTH), FRAME_WIDTH, FRAME_HEIGHT, 0.0)
        tracker.update(observe(make_detection(2, 700), FRAME_WIDTH), FRAME_WIDTH, FRAME_HEIGHT, 0.0)

        first = tracker.update(
            observe(make_detection(1, 470), FRAME_WIDTH),
            FRAME_WIDTH,
            FRAME_HEIGHT,
            timestamp=0.1,
        )
        second = tracker.update(
            observe(make_detection(2, 630), FRAME_WIDTH),
            FRAME_WIDTH,
            FRAME_HEIGHT,
            timestamp=0.1,
        )

        self.assertEqual(first.horizontal_motion, "moving right")
        self.assertEqual(second.horizontal_motion, "moving left")

    def test_detects_left_to_right_crossing(self) -> None:
        tracker = TemporalTracker(history_size=6)
        for index, center_x in enumerate((150, 300, 500, 700, 850)):
            result = tracker.update(
                observe(make_detection(3, center_x), FRAME_WIDTH),
                FRAME_WIDTH,
                FRAME_HEIGHT,
                timestamp=index * 0.1,
            )
        self.assertEqual(result.crossing_trajectory, "left_to_right")

    def test_detects_right_to_left_crossing(self) -> None:
        tracker = TemporalTracker(history_size=6)
        for index, center_x in enumerate((850, 700, 500, 300, 150)):
            result = tracker.update(
                observe(make_detection(4, center_x), FRAME_WIDTH),
                FRAME_WIDTH,
                FRAME_HEIGHT,
                timestamp=index * 0.1,
            )
        self.assertEqual(result.crossing_trajectory, "right_to_left")

    def test_does_not_call_center_only_motion_a_crossing(self) -> None:
        tracker = TemporalTracker(history_size=6)
        for index, center_x in enumerate((400, 470, 540, 600)):
            result = tracker.update(
                observe(make_detection(5, center_x), FRAME_WIDTH),
                FRAME_WIDTH,
                FRAME_HEIGHT,
                timestamp=index * 0.1,
            )
        self.assertIsNone(result.crossing_trajectory)

    def test_structured_event_contains_temporal_state(self) -> None:
        tracker = TemporalTracker(history_size=6)
        tracker.update(
            observe(make_detection(6, 150), FRAME_WIDTH),
            FRAME_WIDTH,
            FRAME_HEIGHT,
            timestamp=0.0,
        )
        tracker.update(
            observe(make_detection(6, 500), FRAME_WIDTH),
            FRAME_WIDTH,
            FRAME_HEIGHT,
            timestamp=0.1,
        )
        result = tracker.update(
            observe(make_detection(6, 850), FRAME_WIDTH),
            FRAME_WIDTH,
            FRAME_HEIGHT,
            timestamp=0.2,
        )

        event = tracker.to_event(result, source="camera-test")
        payload = event.as_dict()

        self.assertEqual(event.event_type, "crossing")
        self.assertEqual(event.crossing_trajectory, "left_to_right")
        self.assertEqual(event.track_id, 6)
        self.assertEqual(event.clock_position, 3)
        self.assertEqual(event.source, "camera-test")
        self.assertEqual(payload["schema_version"], "1.0")


if __name__ == "__main__":
    unittest.main()
