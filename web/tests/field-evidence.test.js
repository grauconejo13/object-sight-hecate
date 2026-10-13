import test from "node:test";
import assert from "node:assert/strict";
import { createFieldEvidenceLog } from "../src/field-evidence.js";

test("records an analysis without retaining a camera frame or bounding box", () => {
  const times = [new Date("2026-10-12T21:00:00Z"), new Date("2026-10-12T21:00:03Z")];
  const log = createFieldEvidenceLog({ now: () => times.shift() });
  log.recordAnalysis({
    mode: "live",
    result: {
      width: 960,
      height: 720,
      inference_ms: 153,
      observations: [{ label: "person", confidence: 0.92, position: "ahead", clock: 12, box: [1, 2, 3, 4] }],
    },
  });

  assert.equal(log.count, 1);
  assert.deepEqual(log.exportPayload(), {
    format: "hecate-field-evidence/v1",
    exported_at: "2026-10-12T21:00:03.000Z",
    privacy: "No image frames or audio are included. This file contains only model outputs and timing metadata.",
    session: [{
      timestamp: "2026-10-12T21:00:00.000Z",
      mode: "live",
      image: { width: 960, height: 720 },
      inference_ms: 153,
      observation_count: 1,
      observations: [{ label: "person", confidence: 0.92, position: "ahead", clock: 12 }],
    }],
  });
});
