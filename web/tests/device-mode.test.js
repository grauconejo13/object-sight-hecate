import assert from "node:assert/strict";
import test from "node:test";
import { caption, createDevicePoller, describeDeviceStatus, pickAlertToSpeak, settingsFromForm } from "../src/device-mode.js";

const settings = { mounting: "backward", paused: false };

test("status explains waiting, offline, paused and live states", () => {
  assert.match(describeDeviceStatus(null), /Connecting/);
  assert.match(describeDeviceStatus({ online: false, last_seen_s: null, settings }), /first frame/);
  assert.match(describeDeviceStatus({ online: false, last_seen_s: 42, settings }), /offline · last seen 42 s ago/);
  assert.match(describeDeviceStatus({ online: true, last_seen_s: 0.3, settings: { ...settings, paused: true } }), /paused/);
  assert.equal(describeDeviceStatus({ online: true, last_seen_s: 0.3, fps: 2.4, settings }), "ESP32 live · 2.4 fps · facing behind you");
});

test("warnings beat notices and cut through the cooldown", () => {
  const alerts = [
    { id: 4, priority: "info", message: "Person behind you" },
    { id: 5, priority: "warn", message: "Person closing in" },
    { id: 6, priority: "info", message: "Dog behind you" },
  ];
  const picked = pickAlertToSpeak(alerts, { lastSpokenId: 3, lastSpokenAt: 1000, now: 2000 });
  assert.equal(picked.alert.id, 5);
  assert.equal(picked.lastSpokenId, 6);
});

test("notices wait out the cooldown but are not replayed later", () => {
  const alerts = [{ id: 2, priority: "info", message: "Person behind you" }];
  const held = pickAlertToSpeak(alerts, { lastSpokenId: 1, lastSpokenAt: 1000, now: 2000 });
  assert.equal(held.alert, null);
  assert.equal(held.lastSpokenId, 2);
  assert.equal(pickAlertToSpeak(alerts, { lastSpokenId: 2, now: 99999 }).alert, null);
});

test("caption keeps steady range quiet and shows approaching", () => {
  const base = { label: "person", track_id: 3, clock: 6, confidence: 0.81 };
  assert.equal(caption({ ...base, range_trend: "steady" }), "person #3 · 6 o'clock · 81%");
  assert.equal(caption({ ...base, range_trend: "approaching" }), "person #3 · 6 o'clock · approaching · 81%");
});

test("form values become typed settings", () => {
  assert.deepEqual(settingsFromForm({
    mounting: "forward", frame_size: "SVGA", jpeg_quality: "15", interval_ms: "600", vflip: true, hmirror: false, paused: false,
  }), { mounting: "forward", frame_size: "SVGA", jpeg_quality: 15, interval_ms: 600, vflip: true, hmirror: false, paused: false });
});

function fakeBackend(snapshots) {
  const calls = [];
  const fetchImpl = async (url) => {
    calls.push(url);
    if (url.includes("frame.jpg")) return { ok: true, blob: async () => `blob:${url}` };
    const body = snapshots.shift();
    return { ok: true, status: 200, json: async () => body };
  };
  return { calls, fetchImpl };
}

test("poller fetches a frame only when the sequence advances and skips old alerts", async () => {
  const snaps = [
    { result: { seq: 1 }, alerts: [{ id: 7 }] },
    { result: { seq: 1 }, alerts: [] },
    { result: { seq: 2 }, alerts: [{ id: 8 }] },
  ];
  const { calls, fetchImpl } = fakeBackend(snaps);
  const seen = [];
  const frames = [];
  const timers = [];
  const poller = createDevicePoller({
    apiBase: "https://api",
    fetchImpl,
    onSnapshot: (s) => seen.push(s.alerts.map((a) => a.id)),
    onFrame: (blob) => frames.push(blob),
    onError: (e) => { throw e; },
    setTimer: (fn) => { timers.push(fn); return timers.length; },
    clearTimer: () => {},
  });
  poller.start();
  for (let i = 0; i < 3; i++) {
    await new Promise((r) => setImmediate(r));
    if (i < 2) await timers.shift()();
  }
  await new Promise((r) => setImmediate(r));
  assert.deepEqual(seen, [[], [], [8]]);
  assert.equal(frames.length, 2);
  assert.ok(calls.includes("https://api/v1/esp32/latest?after_alert=7"));
  poller.stop();
  assert.equal(poller.running, false);
});
