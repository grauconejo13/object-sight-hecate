import unittest

from object_sight_hecate.spatial.position import horizontal_position


class HorizontalPositionTests(unittest.TestCase):
    def test_left_third_maps_to_nine_oclock(self) -> None:
        self.assertEqual(horizontal_position(0.10), ("left", 9))

    def test_middle_third_maps_ahead(self) -> None:
        self.assertEqual(horizontal_position(0.50), ("ahead", 12))

    def test_right_third_maps_to_three_oclock(self) -> None:
        self.assertEqual(horizontal_position(0.90), ("right", 3))


if __name__ == "__main__":
    unittest.main()


class PlausibilityTests(unittest.TestCase):
    def test_unlikely_classes_need_high_confidence(self) -> None:
        from object_sight_hecate.vision.detector import is_plausible

        self.assertFalse(is_plausible("train", 0.6))
        self.assertTrue(is_plausible("train", 0.9))
        self.assertTrue(is_plausible("person", 0.36))
        self.assertTrue(is_plausible("car", 0.5))
