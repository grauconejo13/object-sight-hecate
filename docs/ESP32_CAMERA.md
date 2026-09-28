# ESP32-S3 CameraWebServer input

The existing Hecate Python detector runs on the laptop. The ESP32-S3 serves camera frames over Wi-Fi; it does not run the YOLO model.

## Run on the same Wi-Fi network

1. Flash Espressif's CameraWebServer example with the camera board model matching your hardware (the current sketch uses `CAMERA_MODEL_ESP32S3_EYE`). Enter your Wi-Fi credentials in the sketch locally; never commit them.
2. Open Serial Monitor and record the board's IP address, for example `192.168.1.25`. Test `http://192.168.1.25/` in a browser.
3. From the laptop, try continuous MJPEG first:

   ```powershell
   python main.py --source "http://192.168.1.25:81/stream"
   ```

4. If OpenCV cannot open or reliably read the stream, use the JPEG snapshot endpoint:

   ```powershell
   python main.py --source "http://192.168.1.25/capture"
   ```

The snapshot input requests and decodes one JPEG at a time with a three-second network timeout and an 8 MiB response limit. The stream path uses OpenCV's existing `VideoCapture` support. Both sources feed the same detector and on-screen overlay. The ESP32 chooses its own capture size, so the laptop's usual 1280x720 webcam request does not control its resolution.

Press `q` or `Esc` to close the display. Test with steady indoor light first, then compare the original and wide-angle lens. Check whether left/center/right in the image matches the direction you intend to give the wearer; a camera mounted facing backward will need a deliberate orientation convention before spoken alerts are trustworthy.

## Troubleshooting

- Verify the board and laptop are on the same Wi-Fi network. Guest Wi-Fi may isolate devices.
- The example's `/capture` endpoint is usually on the web UI port (80), while `/stream` is usually on port 81; check the URLs shown by your sketch if customized.
- If `/stream` cannot open, try `/capture`. If both fail, open each URL in the laptop browser and check board IP and power.
- Lower frame size/JPEG quality in the CameraWebServer UI if the feed stalls. Snapshot mode trades frame rate for simpler debugging.
- Detection labels, left/center/right zones, and FPS are prototype outputs. Distance, approach direction, and safety alerts are not implemented yet.

No internet-facing port forwarding is needed for this local test. Do not put a private camera IP, Wi-Fi password, or captured frames in the repository.
