import assert from "node:assert/strict";
import test from "node:test";
import { PersonTracks } from "../src/person-tracks.js";

const person = (x, confidence = 0.8) => ({
  label: "person", confidence, box: [x, 10, x + 20, 70], clock: x > 50 ? 3 : 9,
});

test("two nearby people retain separate screen tracks, and a missing focused person is lost", () => {
  const tracker = new PersonTracks();
  let result = tracker.update([person(10), person(70)], 100, 100);
  assert.equal(result.visible.length, 2);
  const [leftId, rightId] = result.visible.map((track) => track.id);
  result = tracker.update([person(12), person(68)], 100, 100);
  assert.deepEqual(result.visible.map((track) => track.id), [leftId, rightId]);
  result = tracker.update([person(70)], 100, 100);
  assert.deepEqual(result.lost, []);
  result = tracker.update([person(70)], 100, 100);
  assert.deepEqual(result.lost, []);
  result = tracker.update([person(70)], 100, 100);
  assert.deepEqual(result.lost, [leftId]);
  assert.equal(result.visible[0].id, rightId);
});

test("weak person guesses and unrelated objects never create person tracks", () => {
  const tracker = new PersonTracks();
  assert.deepEqual(tracker.update([person(15, 0.42), { ...person(70), label: "dog" }], 100, 100).visible, []);
});
