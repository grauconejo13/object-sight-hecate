import assert from "node:assert/strict";
import test from "node:test";
import { readFlag, soundCheckMessage, supportsVibration, vibrateFor, writeFlag, VIBRATION_PATTERNS } from "../src/feedback.js";

function fakeNavigator() {
  const calls = [];
  return { calls, vibrate: (pattern) => { calls.push(pattern); return true; } };
}

test("vibrates only when supported and enabled", () => {
  const nav = fakeNavigator();
  assert.equal(vibrateFor("warn", { nav }), true);
  assert.deepEqual(nav.calls[0], VIBRATION_PATTERNS.warn);
  assert.equal(vibrateFor("warn", { nav, enabled: false }), false);
  assert.equal(vibrateFor("unknown-kind", { nav }), false);
  assert.equal(vibrateFor("warn", { nav: {} }), false);
  assert.equal(supportsVibration({}), false);
  assert.equal(nav.calls.length, 1);
});

test("a throwing vibrate call is treated as unsupported", () => {
  assert.equal(vibrateFor("warn", { nav: { vibrate: () => { throw new Error("blocked"); } } }), false);
});

test("flags survive missing or throwing storage", () => {
  const store = new Map();
  const storage = { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, v) };
  assert.equal(readFlag(storage, "x", true), true);
  writeFlag(storage, "x", false);
  assert.equal(readFlag(storage, "x", true), false);
  const broken = { getItem() { throw new Error("denied"); }, setItem() { throw new Error("denied"); } };
  assert.equal(readFlag(broken, "x", false), false);
  assert.doesNotThrow(() => writeFlag(broken, "x", true));
  assert.equal(readFlag(undefined, "x", true), true);
});

test("sound check explains what to check", () => {
  assert.match(soundCheckMessage({ canSpeak: false }), /can't speak/);
  assert.match(soundCheckMessage({ canSpeak: true, soundOn: true, vibrated: true }), /felt a buzz/);
  assert.match(soundCheckMessage({ canSpeak: true, soundOn: false, vibrated: false }), /Sound is off/);
});
