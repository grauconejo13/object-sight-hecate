import "./style.css";
import { PersonTracks } from "./person-tracks.js";
import { createFieldEvidenceLog } from "./field-evidence.js";
import {
  FRAME_SIZES, INTERVALS_MS, applyStatus, caption, createDevicePoller, describeDeviceStatus, pickAlertToSpeak, settingsFromForm,
} from "./device-mode.js";
import { askButtonLabel, briefingTag, phoneBriefingRequest } from "./briefing.js";

const video = document.querySelector("#camera");
const canvas = document.querySelector("#snapshot");
const overlay = document.querySelector("#overlay");
const placeholder = document.querySelector("#camera-placeholder");
const badge = document.querySelector(".badge");
const startButton = document.querySelector("#start");
const switchButton = document.querySelector("#switch");
const analyzeButton = document.querySelector("#analyze");
const liveButton = document.querySelector("#live");
const stopButton = document.querySelector("#stop");
const status = document.querySelector("#status");
const cameraStatus = document.querySelector("#camera-status");
const list = document.querySelector("#observations");
const speakToggle = document.querySelector("#voice");
const backButton = document.querySelector("#back-mode");
const focusButton = document.querySelector("#focus-person");
const listenButton = document.querySelector("#listen-command");
const backStatus = document.querySelector("#back-status");
const exportEvidenceButton = document.querySelector("#export-evidence");
const evidenceCount = document.querySelector("#evidence-count");
const apiBase = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
const MISSING_API_URL = "No backend URL. Put VITE_API_URL in web/.env.local and restart npm run dev (on Vercel: project environment variables, then redeploy).";
const sourcePhoneButton = document.querySelector("#source-phone");
const sourceEsp32Button = document.querySelector("#source-esp32");
const deviceFrame = document.querySelector("#device-frame");
const deviceWatchButton = document.querySelector("#device-watch");
const deviceSettingsOpen = document.querySelector("#device-settings-open");
const deviceSettingsDialog = document.querySelector("#device-settings");
const deviceSettingsForm = document.querySelector("#device-settings-form");
const deviceSettingsStatus = document.querySelector("#device-settings-status");
const deviceSettingsClose = document.querySelector("#device-settings-close");
const qualityValue = document.querySelector("#quality-value");
const askButton = document.querySelector("#ask-hecate");
const saveSettingsButton = document.querySelector("#device-settings-save");
const moreOpenButton = document.querySelector("#more-open");
const moreSheet = document.querySelector("#more-sheet");
const moreCloseButton = document.querySelector("#more-close");
const briefingPanel = document.querySelector("#briefing");
const briefingText = document.querySelector("#briefing-text");
const briefingTagLine = document.querySelector("#briefing-tag");
const briefingClose = document.querySelector("#briefing-close");
let lastPhoneItems = null;

let stream = null;
let cameraFacing = "environment";
let switching = false;
let busy = false;
let live = false;
let liveTimer = null;
let currentRequest = null;
let lastLiveResult = null;
const SPEECH_COOLDOWN_MS = 8000;
const REPEAT_SPEECH_MS = 30000;
const LIVE_SPEECH_CONFIDENCE = 0.55;
let previousSpokenCandidates = new Set();
let lastSpokenAt = 0;
const spokenAt = new Map();
const personTracks = new PersonTracks();
const evidenceLog = createFieldEvidenceLog();
let backMode = false;
let focusedId = null;
let listening = false;
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognizer = null;

function say(message) {
  if (!speakToggle.checked || !("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(new SpeechSynthesisUtterance(message));
}

function resetBackMode() {
  backMode = false;
  focusedId = null;
  personTracks.reset();
  recognizer?.abort();
  backStatus.textContent = "Off. Camera positions are relative to the rear camera view.";
  updateButtons();
}

function processPersonTracks(items, width, height) {
  const { visible, lost } = personTracks.update(items, width, height);
  if (!backMode) return;
  if (focusedId !== null && lost.includes(focusedId)) {
    focusedId = null;
    say("Track lost.");
  }
  for (const track of visible) {
    if (track.samples.length < 2) continue;
    if (!track.announced) {
      // Prioritize one new person per response rather than interrupting every announcement.
      if (Date.now() - lastSpokenAt >= SPEECH_COOLDOWN_MS) {
        say(`Person ${track.id} at ${track.item.clock} o'clock in camera view.`);
        lastSpokenAt = Date.now();
        track.announced = true;
      }
    }
    if (focusedId === track.id && ["larger in view", "smaller in view"].includes(track.motion)
        && track.motion !== track.lastMotionAnnounced
        && Date.now() - lastSpokenAt >= SPEECH_COOLDOWN_MS) {
      say(`Focused person looks ${track.motion} in the camera view.`);
      track.lastMotionAnnounced = track.motion;
      lastSpokenAt = Date.now();
    }
  }
  backStatus.textContent = focusedId === null
    ? `${visible.length} person track(s) in camera view. Tap Focus person to select one.`
    : visible.some((track) => track.id === focusedId)
      ? `Following person in camera view · track ${focusedId}. Size changes can result from camera movement.`
      : `Waiting for focused track ${focusedId} to reappear.`;
}

function focusPerson() {
  const candidates = personTracks.tracks.filter((track) => track.missed === 0 && track.samples.length >= 2);
  if (!candidates.length) { backStatus.textContent = "No stable person detected to focus on."; return; }
  const index = candidates.findIndex((track) => track.id === focusedId);
  const chosen = candidates[(index + 1) % candidates.length];
  focusedId = chosen.id;
  backStatus.textContent = `Following person in camera view · track ${focusedId}.`;
  say(`Focus set. Person ${chosen.id} at ${chosen.item.clock} o'clock in camera view.`);
  if (lastLiveResult) drawLiveDetections(lastLiveResult.items, lastLiveResult.imageWidth, lastLiveResult.imageHeight);
}

function resetLiveSpeech() {
  previousSpokenCandidates.clear();
  spokenAt.clear();
  lastSpokenAt = 0;
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
}

function speakResult(item) {
  say(`${item.label} ${item.position}.`);
}

function speakLiveResult(items) {
  if (!speakToggle.checked || !("speechSynthesis" in window)) return;
  const candidates = items.filter((item) => {
    if (item.confidence < LIVE_SPEECH_CONFIDENCE) return false;
    if (item.label !== "person") return true;
    const track = personTracks.tracks.find((entry) => entry.missed === 0 && entry.item === item);
    return track && track.motion !== "establishing";
  });
  const keyFor = (item) => {
    const track = personTracks.tracks.find((entry) => entry.missed === 0 && entry.item === item);
    return track ? `person:${track.id}:${track.motion}:${item.position}` : `${item.label}:${item.position}`;
  };
  const current = new Set(candidates.map(keyFor));
  const now = Date.now();
  const newItem = candidates.find((item) => {
    const key = keyFor(item);
    return previousSpokenCandidates.has(key) && now - (spokenAt.get(key) || 0) >= REPEAT_SPEECH_MS;
  });
  previousSpokenCandidates = current;
  if (!newItem || now - lastSpokenAt < SPEECH_COOLDOWN_MS) return;
  const key = keyFor(newItem);
  const track = personTracks.tracks.find((entry) => entry.missed === 0 && entry.item === newItem);
  if (track) say(`Person ${track.id} at ${newItem.clock} o'clock in camera view. ${track.motion}.`);
  else speakResult(newItem);
  spokenAt.set(key, now);
  lastSpokenAt = now;
}

speakToggle.addEventListener("change", resetLiveSpeech);

function setStatus(message) {
  status.textContent = message;
  cameraStatus.textContent = message;
}

function updateEvidenceExport() {
  const count = evidenceLog.count;
  const label = count === 1 ? "1 field-test entry" : `${count} field-test entries`;
  evidenceCount.textContent = `${label} recorded locally; download when ready.`;
  exportEvidenceButton.disabled = count === 0;
  exportEvidenceButton.setAttribute("aria-label", `Download ${label}`);
  exportEvidenceButton.title = `Download ${label}`;
}

function downloadEvidence() {
  if (!evidenceLog.count) return;
  const blob = new Blob([JSON.stringify(evidenceLog.exportPayload(), null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `hecate-field-evidence-${new Date().toISOString().replace(/[:.]/g, "-")}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
  setStatus(`Downloaded ${evidenceLog.count} field-test entr${evidenceLog.count === 1 ? "y" : "ies"}.`);
}

// Dock buttons keep an icon span, so change only their visible label.
function setControl(button, label, description = label) {
  const labelNode = button.querySelector(".label");
  if (labelNode) labelNode.textContent = label;
  else button.textContent = label;
  button.setAttribute("aria-label", description);
  button.title = description;
}

function updateButtons() {
  startButton.disabled = Boolean(stream) || busy || switching;
  switchButton.disabled = !stream || switching;
  setControl(switchButton, cameraFacing === "environment" ? "Use front camera" : "Use rear camera");
  analyzeButton.disabled = !stream || busy || live || switching;
  liveButton.disabled = !stream || switching;
  setControl(liveButton, live ? "Pause" : "Live", live ? "Stop live analysis" : "Start live analysis");
  liveButton.setAttribute("aria-pressed", String(live));
  stopButton.disabled = !stream || switching;
  backButton.disabled = switching;
  setControl(backButton, backMode ? "Stop Have my back" : "Have my back");
  backButton.setAttribute("aria-pressed", String(backMode));
  focusButton.disabled = !backMode || !live || !personTracks.tracks.some((track) => track.missed === 0 && track.samples.length >= 2);
  listenButton.disabled = !SpeechRecognition || !stream || listening || switching;
  exportEvidenceButton.disabled = evidenceLog.count === 0;
  // Layout state for the dock (see the data-* rules in style.css).
  const body = document.body;
  body.dataset.camera = stream ? "on" : "off";
  body.dataset.back = backMode ? "on" : "off";
  if (body.dataset.source === "phone") body.dataset.live = live ? "on" : "off";
}

function clearOverlay() {
  overlay.getContext("2d").clearRect(0, 0, overlay.width, overlay.height);
  lastLiveResult = null;
}

function stopLiveAnalysis() {
  live = false;
  resetBackMode();
  resetLiveSpeech();
  clearTimeout(liveTimer);
  liveTimer = null;
  currentRequest?.abort();
  currentRequest = null;
  busy = false;
  clearOverlay();
  badge.textContent = "PREVIEW · NO UPLOAD";
  updateButtons();
}

function stopCamera() {
  stopLiveAnalysis();
  stream?.getTracks().forEach((track) => track.stop());
  stream = null;
  video.srcObject = null;
  placeholder.hidden = false;
  canvas.hidden = true;
  clearOverlay();
  badge.textContent = "PREVIEW · NO UPLOAD";
  updateButtons();
}

async function openCamera(requireFacing = false) {
  const nextStream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: { [requireFacing ? "exact" : "ideal"]: cameraFacing }, width: { ideal: 960 } },
    audio: false,
  });
  stream = nextStream;
  video.srcObject = nextStream;
  try {
    await video.play();
  } catch (error) {
    nextStream.getTracks().forEach((track) => track.stop());
    stream = null;
    video.srcObject = null;
    throw error;
  }
  placeholder.hidden = true;
  canvas.hidden = true;
  clearOverlay();
  badge.textContent = "PREVIEW · NO UPLOAD";
}

startButton.addEventListener("click", async () => {
  if (!navigator.mediaDevices?.getUserMedia) {
    setStatus("Camera access needs HTTPS and a supported browser.");
    return;
  }
  try {
    await openCamera();
    setStatus("Camera ready. Tap Analyze one frame or Start live analysis.");
  } catch (error) {
    stopCamera();
    setStatus(`Could not start camera: ${error.message}`);
  }
  updateButtons();
});

switchButton.addEventListener("click", async () => {
  if (!stream || switching) return;
  switching = true;
  stopLiveAnalysis();
  canvas.hidden = true;
  clearOverlay();
  list.replaceChildren();
  const previousFacing = cameraFacing;
  stream.getTracks().forEach((track) => track.stop());
  stream = null;
  video.srcObject = null;
  cameraFacing = previousFacing === "environment" ? "user" : "environment";
  updateButtons();
  try {
    await openCamera(true);
    setStatus(`${cameraFacing === "user" ? "Front" : "Rear"} camera ready.`);
  } catch (error) {
    cameraFacing = previousFacing;
    try {
      await openCamera();
      setStatus(`Could not switch cameras: ${error.message}`);
    } catch (restoreError) {
      stopCamera();
      setStatus(`Could not open a camera: ${restoreError.message}`);
    }
  } finally {
    switching = false;
    updateButtons();
  }
});

stopButton.addEventListener("click", () => {
  stopCamera();
  setStatus("Camera stopped.");
});

function captureJpeg(showSnapshot) {
  const width = video.videoWidth;
  const height = video.videoHeight;
  if (!width || !height) throw new Error("Camera frame is not ready yet.");
  const scale = Math.min(1, 960 / width, 960 / height);
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
  canvas.hidden = !showSnapshot;
  badge.textContent = showSnapshot ? "ANALYZING FRAME" : "LIVE ANALYSIS · PHONE";
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => blob ? resolve(blob) : reject(new Error("Unable to capture JPEG.")),
      "image/jpeg",
      0.75,
    );
  });
}

const TAG_FONT = "'DM Mono', ui-monospace, monospace";
const AQUA = "#9df0dc";
const AMBER = "#ffcb82";

function strokeTarget(ctx, x, y, width, height, highlight) {
  ctx.save();
  ctx.strokeStyle = highlight ? AMBER : AQUA;
  ctx.lineWidth = highlight ? 3 : 2;
  ctx.shadowColor = highlight ? "rgba(255, 203, 130, 0.45)" : "rgba(157, 240, 220, 0.35)";
  ctx.shadowBlur = 12;
  ctx.strokeRect(x, y, width, height);
  ctx.restore();
}

function drawTag(ctx, label, x, y, fontSize, highlight, maxRight) {
  const padX = 7;
  const width = Math.min(ctx.measureText(label).width + padX * 2, maxRight - x);
  ctx.fillStyle = highlight ? AMBER : AQUA;
  ctx.fillRect(x, y, width, fontSize + 10);
  ctx.fillStyle = "#06201c";
  ctx.fillText(label, x + padX, y + fontSize + 2, width - padX * 2);
}

function drawDetections(items, imageWidth, imageHeight) {
  const ctx = canvas.getContext("2d");
  const scaleX = canvas.width / imageWidth;
  const scaleY = canvas.height / imageHeight;
  const fontSize = Math.max(13, Math.round(canvas.width / 55));
  ctx.font = `500 ${fontSize}px ${TAG_FONT}`;
  ctx.lineWidth = Math.max(2, Math.round(canvas.width / 400));

  for (const item of items.slice(0, 12)) {
    const [x1, y1, x2, y2] = item.box;
    const x = x1 * scaleX;
    const y = y1 * scaleY;
    const width = (x2 - x1) * scaleX;
    const height = (y2 - y1) * scaleY;
    strokeTarget(ctx, x, y, width, height, false);
    const label = `${item.label} ${Math.round(item.confidence * 100)}%`.toUpperCase();
    const labelY = y >= fontSize + 12 ? y - fontSize - 10 : y;
    drawTag(ctx, label, x, labelY, fontSize, false, canvas.width);
  }
  badge.textContent = "LAST FRAME · ANALYZED";
}

function drawLiveDetections(items, imageWidth, imageHeight) {
  lastLiveResult = { items, imageWidth, imageHeight };
  const rect = overlay.getBoundingClientRect();
  const pixelRatio = window.devicePixelRatio || 1;
  overlay.width = Math.round(rect.width * pixelRatio);
  overlay.height = Math.round(rect.height * pixelRatio);
  const ctx = overlay.getContext("2d");
  ctx.scale(pixelRatio, pixelRatio);
  const scale = Math.min(rect.width / imageWidth, rect.height / imageHeight);
  const offsetX = (rect.width - imageWidth * scale) / 2;
  const offsetY = (rect.height - imageHeight * scale) / 2;
  const fontSize = Math.max(11, Math.round(rect.width / 34));
  ctx.font = `500 ${fontSize}px ${TAG_FONT}`;
  for (const item of items.slice(0, 12)) {
    const [x1, y1, x2, y2] = item.box;
    const x = offsetX + x1 * scale;
    const y = offsetY + y1 * scale;
    const track = personTracks.tracks.find((entry) => entry.missed === 0 && entry.item === item);
    const focused = (backMode && track?.id === focusedId) || item.highlight;
    strokeTarget(ctx, x, y, (x2 - x1) * scale, (y2 - y1) * scale, focused);
    const label = (item.caption ?? (track
      ? `person #${track.id} · ${track.motion} · ${Math.round(item.confidence * 100)}%`
      : `${item.label} ${Math.round(item.confidence * 100)}%`)).toUpperCase();
    const labelY = y >= fontSize + 12 ? y - fontSize - 10 : y;
    // Keep tags clear of the status pill at the top of the scene.
    const safeLabelY = labelY < 50 ? Math.max(50, y + 4) : labelY;
    drawTag(ctx, label, x, safeLabelY, fontSize, focused, rect.width);
  }
}

window.addEventListener("resize", () => {
  if (lastLiveResult) {
    drawLiveDetections(lastLiveResult.items, lastLiveResult.imageWidth, lastLiveResult.imageHeight);
  }
});

async function analyzeFrame(isLive = false) {
  if (!apiBase) {
    setStatus(MISSING_API_URL);
    if (isLive) stopLiveAnalysis();
    return;
  }
  busy = true;
  updateButtons();
  list.replaceChildren();
  if (!isLive || !lastLiveResult) setStatus("Analyzing one frame…");
  const request = new AbortController();
  currentRequest = request;
  try {
    const jpeg = await captureJpeg(!isLive);
    if (request.signal.aborted) return;
    const response = await fetch(`${apiBase}/v1/analyze`, {
      method: "POST",
      headers: { "Content-Type": "image/jpeg" },
      body: jpeg,
      signal: request.signal,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    if (request.signal.aborted || !stream) return;

    const items = data.observations.sort((a, b) => b.confidence - a.confidence);
    evidenceLog.recordAnalysis({
      mode: backMode ? "have-my-back" : isLive ? "live" : "single-frame",
      result: { ...data, observations: items },
    });
    updateEvidenceExport();
    if (isLive) {
      processPersonTracks(items, data.width, data.height);
      lastPhoneItems = items.map((item) => {
        const track = personTracks.tracks.find((entry) => entry.missed === 0 && entry.item === item);
        return track ? { ...item, motion: track.motion } : item;
      });
      drawLiveDetections(items, data.width, data.height);
      if (!backMode) speakLiveResult(items);
    } else {
      drawDetections(items, data.width, data.height);
      lastPhoneItems = items;
    }
    setStatus(items.length
      ? `${items.length} observation(s) · ${data.inference_ms} ms server processing`
      : `No objects found · ${data.inference_ms} ms server processing`);
    for (const item of items.slice(0, 12)) {
      const row = document.createElement("li");
      const track = isLive && personTracks.tracks.find((entry) => entry.missed === 0 && entry.item === item);
      row.textContent = track
        ? `person #${track.id} · ${track.motion} · ${item.position} (${item.clock} o'clock) · ${Math.round(item.confidence * 100)}%`
        : `${item.label} · ${item.position} (${item.clock} o'clock) · ${Math.round(item.confidence * 100)}%`;
      list.append(row);
    }
    if (!isLive && items.length) speakResult(items[0]);
  } catch (error) {
    if (request.signal.aborted) return;
    canvas.hidden = true;
    clearOverlay();
    badge.textContent = "PREVIEW · NO UPLOAD";
    setStatus(`Analysis failed: ${error.message}`);
    if (isLive) stopLiveAnalysis();
  } finally {
    if (currentRequest === request) {
      currentRequest = null;
      busy = false;
    }
    updateButtons();
    if (isLive && live && stream && !request.signal.aborted) {
      liveTimer = setTimeout(() => analyzeFrame(true), 700);
    }
  }
}

analyzeButton.addEventListener("click", () => analyzeFrame());
liveButton.addEventListener("click", () => {
  if (live) {
    stopLiveAnalysis();
    setStatus("Live analysis stopped.");
  } else {
    live = true;
    canvas.hidden = true;
    clearOverlay();
    updateButtons();
    analyzeFrame(true);
  }
});

backButton.addEventListener("click", async () => {
  if (backMode) {
    stopLiveAnalysis();
    setStatus("Have my back stopped.");
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    setStatus("Camera access needs HTTPS and a supported browser.");
    return;
  }
  try {
    if (stream && cameraFacing !== "environment") {
      stopLiveAnalysis();
      stream.getTracks().forEach((track) => track.stop());
      stream = null;
      video.srcObject = null;
    }
    cameraFacing = "environment";
    if (!stream) await openCamera(true);
    if (live) stopLiveAnalysis();
    speakToggle.checked = true;
    resetLiveSpeech();
    personTracks.reset();
    backMode = true;
    live = true;
    canvas.hidden = true;
    backStatus.textContent = "Watching through the rear camera. Positions refer to its view.";
    updateButtons();
    analyzeFrame(true);
  } catch (error) {
    stopCamera();
    setStatus(`Could not start Have my back: ${error.message}`);
  }
});

focusButton.addEventListener("click", focusPerson);
exportEvidenceButton.addEventListener("click", downloadEvidence);

if (!SpeechRecognition) {
  listenButton.title = "Voice commands are unavailable in this browser. Use the buttons instead.";
}
listenButton.addEventListener("click", () => {
  if (!SpeechRecognition || !stream || listening) return;
  recognizer = new SpeechRecognition();
  recognizer.lang = "en-US";
  recognizer.continuous = false;
  recognizer.interimResults = false;
  recognizer.onresult = (event) => {
    const command = event.results[0][0].transcript.toLowerCase().trim();
    if (/have my back/.test(command) && !backMode) backButton.click();
    else if (/have my back/.test(command)) backStatus.textContent = "Have my back is already on.";
    else if (/\b(track|focus)\b/.test(command) && backMode) focusPerson();
    else if (/\bstop\b/.test(command) && backMode) backButton.click();
    else backStatus.textContent = `Command not recognized: ${command}. Try “focus” or “stop”.`;
  };
  recognizer.onerror = (event) => { backStatus.textContent = `Voice command unavailable: ${event.error}. Use the buttons.`; };
  recognizer.onend = () => { listening = false; updateButtons(); };
  try {
    recognizer.start();
    listening = true;
    backStatus.textContent = "Listening once for Have my back, focus, track, or stop…";
    updateButtons();
  } catch (error) {
    backStatus.textContent = `Could not start voice command: ${error.message}`;
  }
});

// --- Wearable ESP32 camera -------------------------------------------------

const SOURCE_KEY = "hecate.source";
let source = "phone";
let deviceSnapshot = null;
let deviceSettingsDirty = false;
let pendingApply = null; // { settings, at } after Save, until the camera confirms.
let lastDeviceAlertId = 0;
let lastDeviceSpokenAt = 0;
let deviceFrameUrl = null;
let wakeLock = null;

const devicePoller = createDevicePoller({
  apiBase,
  onSnapshot: handleDeviceSnapshot,
  onFrame: showDeviceFrame,
  onError: (error) => setStatus(`Can't reach the backend: ${error.message}. Is Tailscale on?`),
});

for (const option of FRAME_SIZES) deviceSettingsForm.frame_size.add(new Option(option.label, option.value));
for (const option of INTERVALS_MS) deviceSettingsForm.interval_ms.add(new Option(option.label, String(option.value)));

function setSource(next) {
  if (next === source) return;
  if (next === "esp32") {
    stopCamera();
  } else {
    stopDeviceWatch();
    deviceFrame.hidden = true;
  }
  source = next;
  lastPhoneItems = null;
  briefingPanel.hidden = true;
  document.body.dataset.source = next;
  sourcePhoneButton.setAttribute("aria-checked", String(next === "phone"));
  sourceEsp32Button.setAttribute("aria-checked", String(next === "esp32"));
  placeholder.hidden = next === "esp32" && !deviceFrame.hidden;
  placeholder.textContent = next === "esp32"
    ? "Tap Watch to see the wearable camera."
    : "Camera is off. Tap Camera to begin.";
  document.body.dataset.live = "off";
  badge.textContent = next === "esp32" ? "ESP32 CAM · NOT WATCHING" : "PREVIEW · NO UPLOAD";
  list.replaceChildren();
  setStatus(next === "esp32" ? "ESP32 cam selected. Tap Watch to start." : "Phone camera selected.");
  try { localStorage.setItem(SOURCE_KEY, next); } catch { /* storage unavailable */ }
}

async function holdScreenAwake(on) {
  try {
    if (on && "wakeLock" in navigator && !wakeLock) {
      wakeLock = await navigator.wakeLock.request("screen");
      wakeLock.addEventListener("release", () => { wakeLock = null; });
    } else if (!on && wakeLock) {
      await wakeLock.release();
      wakeLock = null;
    }
  } catch { /* Wake Lock is best-effort; speech still works while the page is visible. */ }
}

function startDeviceWatch() {
  if (!apiBase) {
    setStatus(MISSING_API_URL);
    return;
  }
  speakToggle.checked = true;
  resetLiveSpeech();
  // Speaking inside the tap unlocks speech on mobile browsers for later alerts.
  say("Hecate watching.");
  lastDeviceSpokenAt = 0;
  devicePoller.start();
  holdScreenAwake(true);
  deviceWatchButton.setAttribute("aria-pressed", "true");
  setControl(deviceWatchButton, "Watching", "Stop watching the ESP32 cam");
  badge.textContent = "ESP32 CAM · CONNECTING";
  setStatus("Connecting to the ESP32 cam…");
}

function stopDeviceWatch() {
  devicePoller.stop();
  holdScreenAwake(false);
  deviceWatchButton.setAttribute("aria-pressed", "false");
  setControl(deviceWatchButton, "Watch", "Watch ESP32 cam");
  if (source === "esp32") document.body.dataset.live = "off";
  if (source === "esp32") badge.textContent = "ESP32 CAM · NOT WATCHING";
  clearOverlay();
}

function handleDeviceSnapshot(snapshot) {
  deviceSnapshot = snapshot;
  let statusText = describeDeviceStatus(snapshot);
  if (pendingApply) {
    const apply = applyStatus({ saved: pendingApply.settings, applied: snapshot.applied, savedAt: pendingApply.at });
    if (deviceSettingsDialog.open) deviceSettingsStatus.textContent = apply.text;
    if (apply.state === "applied" && saveSettingsButton.dataset.state === "saved"
        && saveSettingsButton.textContent !== "Camera applied ✓") {
      setSaveButton("saved", "Camera applied ✓");
    } else if ((apply.state === "stuck" || apply.state === "no-report") && saveSettingsButton.dataset.state === "saved") {
      setSaveButton("error", "Not confirmed by camera");
    }
    statusText = apply.text;
    // Keep the confirmation visible briefly, then return to the live status.
    if (apply.state !== "waiting" && Date.now() - pendingApply.at > 15000) pendingApply = null;
    else if (apply.state === "applied") pendingApply.at = Math.min(pendingApply.at, Date.now() - 11000);
  }
  setStatus(statusText);
  document.body.dataset.live = snapshot.online && !snapshot.settings.paused ? "on" : "off";
  badge.textContent = snapshot.online
    ? `ESP32 CAM · ${snapshot.settings.mounting === "forward" ? "FRONT" : "REAR"} · LIVE`
    : "ESP32 CAM · WAITING";

  const { alert, lastSpokenId } = pickAlertToSpeak(snapshot.alerts, {
    lastSpokenId: lastDeviceAlertId,
    lastSpokenAt: lastDeviceSpokenAt,
  });
  lastDeviceAlertId = lastSpokenId;
  if (alert) {
    say(alert.message);
    lastDeviceSpokenAt = Date.now();
  }
}

function showDeviceFrame(blob, result) {
  const url = URL.createObjectURL(blob);
  deviceFrame.onload = () => {
    if (deviceFrameUrl) URL.revokeObjectURL(deviceFrameUrl);
    deviceFrameUrl = url;
    deviceFrame.hidden = false;
    placeholder.hidden = true;
    const items = result.observations.map((item) => ({
      ...item,
      caption: caption(item),
      highlight: item.range_trend === "approaching" && item.samples >= 4,
    }));
    drawLiveDetections(items, result.width, result.height);
    list.replaceChildren(...items.slice(0, 12).map((item) => {
      const row = document.createElement("li");
      row.textContent = `${item.caption} · ${item.position}`;
      return row;
    }));
  };
  deviceFrame.src = url;
  evidenceLog.recordAnalysis({ mode: "esp32", result });
  updateEvidenceExport();
}

function fillDeviceSettings(settings) {
  const form = deviceSettingsForm;
  form.mounting.value = settings.mounting;
  form.frame_size.value = settings.frame_size;
  form.interval_ms.value = String(settings.interval_ms);
  form.jpeg_quality.value = String(settings.jpeg_quality);
  form.vflip.checked = settings.vflip;
  form.hmirror.checked = settings.hmirror;
  form.paused.checked = settings.paused;
  qualityValue.textContent = `(${settings.jpeg_quality})`;
}

async function openDeviceSettings() {
  deviceSettingsDirty = false;
  setSaveButton("idle", "Save to camera");
  deviceSettingsStatus.textContent = "Loading current settings…";
  deviceSettingsDialog.showModal();
  try {
    const response = await fetch(`${apiBase}/v1/esp32/latest`);
    const snapshot = await response.json();
    if (!response.ok) throw new Error(snapshot.detail || `HTTP ${response.status}`);
    if (!deviceSettingsDirty) fillDeviceSettings(snapshot.settings);
    deviceSettingsStatus.textContent = describeDeviceStatus(snapshot);
  } catch (error) {
    deviceSettingsStatus.textContent = `Can't load settings: ${error.message}`;
  }
}

// The Save button itself shows progress, so a tap never looks ignored.
let saveButtonTimer = null;
function setSaveButton(state, text) {
  clearTimeout(saveButtonTimer);
  saveSettingsButton.dataset.state = state;
  saveSettingsButton.textContent = text;
  saveSettingsButton.disabled = state === "saving";
  if (state === "saved" || state === "error") {
    saveButtonTimer = setTimeout(() => setSaveButton("idle", "Save to camera"), 3500);
  }
}

async function saveDeviceSettings(event) {
  event.preventDefault();
  const form = deviceSettingsForm;
  const settings = settingsFromForm({
    mounting: form.mounting.value,
    frame_size: form.frame_size.value,
    interval_ms: form.interval_ms.value,
    jpeg_quality: form.jpeg_quality.value,
    vflip: form.vflip.checked,
    hmirror: form.hmirror.checked,
    paused: form.paused.checked,
  });
  deviceSettingsStatus.textContent = "Saving…";
  setSaveButton("saving", "Saving…");
  try {
    const response = await fetch(`${apiBase}/v1/esp32/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    deviceSettingsDirty = false;
    fillDeviceSettings(data.settings);
    pendingApply = { settings: data.settings, at: Date.now() };
    deviceSettingsStatus.textContent = devicePoller.running
      ? "Saved. Waiting for the camera to apply it…"
      : "Saved. Tap Watch to see when the camera applies it.";
    clearTimeout(saveButtonTimer);
    saveSettingsButton.dataset.state = "saved";
    saveSettingsButton.disabled = false;
    saveSettingsButton.textContent = devicePoller.running ? "Saved · waiting for camera…" : "Saved ✓";
    if (!devicePoller.running) setSaveButton("saved", "Saved ✓");
  } catch (error) {
    deviceSettingsStatus.textContent = `Couldn't save: ${error.message}`;
    setSaveButton("error", "Couldn't save · try again");
  }
}

sourcePhoneButton.addEventListener("click", () => setSource("phone"));
sourceEsp32Button.addEventListener("click", () => setSource("esp32"));
deviceWatchButton.addEventListener("click", () => (devicePoller.running ? stopDeviceWatch() : startDeviceWatch()));
deviceSettingsOpen.addEventListener("click", openDeviceSettings);
deviceSettingsClose.addEventListener("click", () => deviceSettingsDialog.close());
// Some mobile browsers fire only "change" for dropdowns, so listen to both.
for (const type of ["input", "change"]) {
  deviceSettingsForm.addEventListener(type, () => {
    deviceSettingsDirty = true;
    qualityValue.textContent = `(${deviceSettingsForm.jpeg_quality.value})`;
  });
}
deviceSettingsForm.addEventListener("submit", saveDeviceSettings);

// More sheet: secondary phone tools, detections list, evidence export.
moreOpenButton.addEventListener("click", () => moreSheet.showModal());
moreCloseButton.addEventListener("click", () => moreSheet.close());
// Actions that change the camera view close the sheet so the result is visible.
for (const button of [backButton, switchButton, analyzeButton, listenButton]) {
  button.addEventListener("click", () => moreSheet.close());
}
// Tapping the dimmed backdrop closes either sheet.
for (const sheet of [moreSheet, deviceSettingsDialog]) {
  sheet.addEventListener("click", (event) => {
    if (event.target !== sheet) return;
    // Clicks on the sheet's own padding also target the dialog; only close outside it.
    const box = sheet.getBoundingClientRect();
    const inside = event.clientX >= box.left && event.clientX <= box.right
      && event.clientY >= box.top && event.clientY <= box.bottom;
    if (!inside) sheet.close();
  });
}
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && devicePoller.running) holdScreenAwake(true);
});

try {
  if (localStorage.getItem(SOURCE_KEY) === "esp32") setSource("esp32");
} catch { /* storage unavailable */ }

// --- Ask Hecate: optional Nemotron scene briefing ---------------------------
// Runs beside detection, never inside it: live analysis and ESP32 alerts keep
// going while a briefing request is in flight.

let briefingRequest = null;

function showBriefing(text, tag, unavailable = false) {
  briefingText.textContent = text;
  briefingTagLine.textContent = tag;
  briefingPanel.classList.toggle("unavailable", unavailable);
  briefingPanel.hidden = false;
}

async function refreshBriefingStatus() {
  if (!apiBase) return;
  try {
    const response = await fetch(`${apiBase}/v1/briefing/status`);
    const status = await response.json();
    if (!response.ok) throw new Error(status.detail || `HTTP ${response.status}`);
    askButton.title = askButtonLabel(status);
    askButton.setAttribute("aria-label", askButton.title);
    askButton.dataset.nebius = status.available ? "available" : "unavailable";
  } catch {
    askButton.title = "Ask Hecate (backend not reachable)";
    askButton.setAttribute("aria-label", askButton.title);
    askButton.dataset.nebius = "unreachable";
  }
}

async function askHecate() {
  if (briefingRequest) return;
  if (!apiBase) {
    showBriefing(MISSING_API_URL, "Not configured", true);
    return;
  }
  let body;
  if (source === "esp32") {
    body = { source: "esp32" };
  } else if (lastPhoneItems) {
    body = phoneBriefingRequest(lastPhoneItems);
  } else {
    showBriefing("Analyze a frame or start live analysis first, then ask again.", "No scene yet", true);
    return;
  }

  const request = new AbortController();
  const timeout = setTimeout(() => request.abort(), 15000);
  briefingRequest = request;
  askButton.setAttribute("aria-busy", "true");
  showBriefing("Asking Hecate…", askButton.dataset.nebius === "available" ? "NVIDIA Nemotron on Nebius" : "Local summary");
  try {
    const response = await fetch(`${apiBase}/v1/briefing`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: request.signal,
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || `HTTP ${response.status}`);
    showBriefing(result.text, briefingTag(result), result.provider !== "nemotron");
    say(result.text);
  } catch (error) {
    const message = error.name === "AbortError" ? "Briefing timed out." : `Briefing failed: ${error.message}`;
    showBriefing(message, "Live detection is unaffected", true);
  } finally {
    clearTimeout(timeout);
    briefingRequest = null;
    askButton.removeAttribute("aria-busy");
  }
}

askButton.addEventListener("click", askHecate);
briefingClose.addEventListener("click", () => { briefingPanel.hidden = true; });
refreshBriefingStatus();

updateEvidenceExport();
window.addEventListener("pagehide", () => {
  stopCamera();
  stopDeviceWatch();
});
