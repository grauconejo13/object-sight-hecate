"""Camera input behavior without a physical ESP32 on the test machine."""

import unittest
from unittest.mock import patch

import cv2
import numpy as np

from object_sight_hecate.vision.camera import CameraConfig, CameraSource


class CameraSourceTests(unittest.TestCase):
    def test_esp32_snapshot_decodes_a_frame(self):
        image = np.zeros((32, 48, 3), dtype=np.uint8)
        encoded, jpeg = cv2.imencode(".jpg", image)
        self.assertTrue(encoded)

        from io import BytesIO

        with patch(
            "object_sight_hecate.vision.camera.urlopen",
            return_value=BytesIO(jpeg.tobytes()),
        ) as request:
            with CameraSource(CameraConfig(source="http://192.168.1.25/capture")) as camera:
                frame = next(camera.frames())

        self.assertEqual(frame.shape, image.shape)
        request.assert_called_once_with("http://192.168.1.25/capture", timeout=3.0)

    def test_invalid_snapshot_fails_with_clear_error(self):
        from io import BytesIO

        with patch(
            "object_sight_hecate.vision.camera.urlopen",
            return_value=BytesIO(b"not-a-jpeg"),
        ):
            with CameraSource(CameraConfig(source="http://192.168.1.25/capture")) as camera:
                with self.assertRaisesRegex(RuntimeError, "valid JPEG"):
                    next(camera.frames())


if __name__ == "__main__":
    unittest.main()
