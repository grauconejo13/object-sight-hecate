// Wearable ESP32 camera mode: DOM-free helpers so the logic is testable in Node.

export const FRAME_SIZES = [
  { value: "QVGA", label: "320×240 · fastest" },
  { value: "VGA", label: "640×480 · balanced" },
  { value: "SVGA", label: "800×600" },
  { value: "HD", label: "1280×720 · sharpest" },
];

export const INTERVALS_MS = [
  { value: 150, label: "~6 fps" },
  { value: 250, label: "~4 fps" },
  { value: 400, label: "~2.5 fps" },
  { value: 600, label: "~1.5 fps" },
  { value: 1000, label: "1 fps" },
  { value: 2000, label: "0.5 fps · saves data" },
];

export function describeDeviceStatus(snapshot) {
  if (!snapshot) return "Connecting to the backend…";
  const { online, last_seen_s: age, fps, settings } = snapshot;
  if (age === null || age === undefined) return "Waiting for the ESP32 cam to send its first frame…";
  if (settings?.paused && online) return "ESP32 paused from the app. Resume in camera settings.";
  if (!online) return `ESP32 offline · last seen ${formatAge(age)} ago. Check its power bank and your hotspot.`;
  const mount = settings?.mounting === "forward" ? "facing forward" : "facing behind you";
  const rate = fps ? ` · ${fps} fps` : "";
  return `ESP32 live${rate} · ${mount}`;
}

function formatAge(seconds) {
  if (seconds < 90) return `${Math.round(seconds)} s`;
  return `${Math.round(seconds / 60)} min`;
}

/**
 * Pick at most one alert to speak from those not yet heard.
 * Warnings interrupt the cooldown; a backlog after a pause collapses to the
 * most important recent alert instead of reading out stale history.
 */
export function pickAlertToSpeak(alerts, { lastSpokenId = 0, lastSpokenAt = 0, now = Date.now(), cooldownMs = 4000 } = {}) {
  const unheard = (alerts || []).filter((alert) => alert.id > lastSpokenId);
  if (!unheard.length) return { alert: null, lastSpokenId };
  const newestId = Math.max(...unheard.map((alert) => alert.id));
  const warnings = unheard.filter((alert) => alert.priority === "warn");
  const candidate = (warnings.length ? warnings : unheard).reduce((a, b) => (b.id > a.id ? b : a));
  const coolingDown = now - lastSpokenAt < cooldownMs;
  if (coolingDown && candidate.priority !== "warn") return { alert: null, lastSpokenId: newestId };
  return { alert: candidate, lastSpokenId: newestId };
}

export function caption(item) {
  const id = item.track_id ?? "?";
  const range = item.range_trend && !["unknown", "steady"].includes(item.range_trend) ? ` · ${item.range_trend}` : "";
  return `${item.label} #${id} · ${item.clock} o'clock${range} · ${Math.round(item.confidence * 100)}%`;
}

/** Coerce raw form values into the backend's settings shape. */
export function settingsFromForm(values) {
  return {
    mounting: values.mounting === "forward" ? "forward" : "backward",
    frame_size: values.frame_size,
    jpeg_quality: Number(values.jpeg_quality),
    interval_ms: Number(values.interval_ms),
    vflip: Boolean(values.vflip),
    hmirror: Boolean(values.hmirror),
    paused: Boolean(values.paused),
  };
}

/**
 * Poll /v1/esp32/latest and fetch a frame only when its sequence number changes.
 * fetchImpl and timers are injectable for tests.
 */
export function createDevicePoller({
  apiBase,
  onSnapshot,
  onFrame,
  onError,
  intervalMs = 500,
  fetchImpl = (...args) => fetch(...args),
  setTimer = (fn, ms) => setTimeout(fn, ms),
  clearTimer = (id) => clearTimeout(id),
}) {
  let running = false;
  let timer = null;
  let controller = null;
  let shownSeq = 0;
  let lastAlertId = 0;
  let primed = false;

  async function tick() {
    if (!running) return;
    controller = new AbortController();
    try {
      const response = await fetchImpl(`${apiBase}/v1/esp32/latest?after_alert=${lastAlertId}`, { signal: controller.signal });
      const snapshot = await response.json();
      if (!response.ok) throw new Error(snapshot.detail || `HTTP ${response.status}`);
      if (!running) return;
      for (const alert of snapshot.alerts || []) lastAlertId = Math.max(lastAlertId, alert.id);
      // Alerts raised before the user started watching are history, not news.
      onSnapshot(primed ? snapshot : { ...snapshot, alerts: [] });
      primed = true;
      const seq = snapshot.result?.seq || 0;
      if (seq > shownSeq) {
        const frame = await fetchImpl(`${apiBase}/v1/esp32/frame.jpg?seq=${seq}`, { signal: controller.signal, cache: "no-store" });
        if (frame.ok && running) {
          shownSeq = seq;
          onFrame(await frame.blob(), snapshot.result);
        }
      }
    } catch (error) {
      if (running && error.name !== "AbortError") onError(error);
    } finally {
      controller = null;
      if (running) timer = setTimer(tick, intervalMs);
    }
  }

  return {
    get running() { return running; },
    start() {
      if (running) return;
      running = true;
      primed = false;
      tick();
    },
    stop() {
      running = false;
      if (timer !== null) clearTimer(timer);
      timer = null;
      controller?.abort();
    },
  };
}
