# Field-test evidence export

Hecate can export a browser-local JSON record of a phone field-test session.

## What it records

Each completed analysis records:

- UTC timestamp
- mode: `single-frame`, `live`, or `have-my-back`
- source image dimensions
- server inference latency
- object labels, confidence, horizontal position, and clock hint

## What it does not record

- Camera frames or video
- Audio
- Location
- Face identity or biometric data
- Measured distance, danger level, or an inference that someone is approaching

The export is designed to support repeatable evaluation: it lets a tester pair a written scenario and observed failure/success with the model's actual response, without retaining raw camera imagery.

## Use during a field test

1. Open Hecate and run a short, defined scenario.
2. Use the download icon in the camera view to export the current session.
3. Save the JSON alongside a short test note: scenario, expected behavior, actual behavior, and any false positives or missed detections.
4. Start a new browser session or refresh the page before an unrelated scenario.

The log stays in browser memory until the page is refreshed. It is never sent to the Hecate API.
