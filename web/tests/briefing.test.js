import assert from "node:assert/strict";
import test from "node:test";
import { askButtonLabel, briefingDetail, briefingTag, phoneBriefingRequest } from "../src/briefing.js";

test("phone request sends only labels, directions, confidence and view-size trend", () => {
  const request = phoneBriefingRequest([
    { label: "person", confidence: 0.9, clock: 12, position: "ahead", box: [1, 2, 3, 4], motion: "larger in view" },
    { label: "car", confidence: 0.7, clock: 3, position: "right", box: [5, 6, 7, 8] },
  ]);
  assert.equal(request.source, "phone");
  assert.deepEqual(request.observations[0], { label: "person", confidence: 0.9, clock: 12, position: "ahead", motion: "larger in view" });
  assert.equal("box" in request.observations[1], false);
});

test("tag shows who wrote the briefing and when Nebius is unavailable", () => {
  assert.equal(briefingTag({ provider: "nemotron", latency_ms: 1430 }), "NVIDIA Nemotron on Nebius · 1.4 s");
  assert.equal(briefingTag({ provider: "nemotron", cached: true, latency_ms: 900 }), "NVIDIA Nemotron on Nebius · cached");
  assert.equal(briefingTag({ provider: "local", nebius: "unavailable" }), "Nebius unavailable · local summary");
  assert.match(briefingTag({ provider: "local", nebius: "guarded" }), /withheld by safety check/);
  assert.equal(briefingTag({ provider: "local", nebius: "error" }), "Nebius error · local summary");
});

test("button label reflects Nebius availability", () => {
  assert.match(askButtonLabel({ available: true }), /Nemotron on Nebius/);
  assert.match(askButtonLabel({ available: false }), /Nebius unavailable/);
});

test("detail explains a fallback in plain words and stays empty for Nemotron", () => {
  assert.equal(briefingDetail({ provider: "nemotron", reason: null }), "");
  assert.equal(briefingDetail({ provider: "local", nebius: "guarded", reason: "Nemotron reply discarded by local guard: named 'train', which is not in the scene facts" }),
    "Reason: named 'train', which is not in the scene facts");
  assert.equal(briefingDetail({ provider: "local", nebius: "error", reason: "Nebius rate limit reached" }), "Nebius rate limit reached");
});
