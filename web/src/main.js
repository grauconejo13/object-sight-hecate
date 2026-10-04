import "./style.css";
import { PersonTracks } from "./person-tracks.js";

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
const apiBase = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

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

function updateButtons() {
  startButton.disabled = Boolean(stream) || busy || switching;
  switchButton.disabled = !stream || switching;
  switchButton.textContent = cameraFacing === "environment" ? "Use front camera" : "Use rear camera";
  switchButton.setAttribute("aria-label", switchButton.textContent);
  switchButton.title = switchButton.textContent;
  analyzeButton.disabled = !stream || busy || live || switching;
  liveButton.disabled = !stream || switching;
  liveButton.textContent = live ? "Stop live analysis" : "Start live analysis";
  liveButton.setAttribute("aria-pressed", String(live));
  liveButton.setAttribute("aria-label", liveButton.textContent);
  liveButton.title = liveButton.textContent;
  stopButton.disabled = !stream || switching;
  backButton.disabled = switching;
  backButton.textContent = backMode ? "Stop Have my back" : "Have my back";
  backButton.setAttribute("aria-pressed", String(backMode));
  backButton.setAttribute("aria-label", backButton.textContent);
  backButton.title = backButton.textContent;
  focusButton.disabled = !backMode || !live || !personTracks.tracks.some((track) => track.missed === 0 && track.samples.length >= 2);
  listenButton.disabled = !SpeechRecognition || !stream || listening || switching;
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
  badge.textContent = "LIVE PREVIEW · NO AUTO UPLOAD";
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
  badge.textContent = "LIVE PREVIEW · NO AUTO UPLOAD";
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
  badge.textContent = "LIVE PREVIEW · NO AUTO UPLOAD";
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
  badge.textContent = showSnapshot ? "ANALYZING CAPTURED FRAME" : "LIVE ANALYSIS · FRAMES SENT REPEATEDLY";
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => blob ? resolve(blob) : reject(new Error("Unable to capture JPEG.")),
      "image/jpeg",
      0.75,
    );
  });
}

function drawDetections(items, imageWidth, imageHeight) {
  const ctx = canvas.getContext("2d");
  const scaleX = canvas.width / imageWidth;
  const scaleY = canvas.height / imageHeight;
  const fontSize = Math.max(13, Math.round(canvas.width / 55));
  ctx.font = `600 ${fontSize}px system-ui, sans-serif`;
  ctx.lineWidth = Math.max(2, Math.round(canvas.width / 400));

  for (const item of items.slice(0, 12)) {
    const [x1, y1, x2, y2] = item.box;
    const x = x1 * scaleX;
    const y = y1 * scaleY;
    const width = (x2 - x1) * scaleX;
    const height = (y2 - y1) * scaleY;
    ctx.strokeStyle = "#86dcc8";
    ctx.strokeRect(x, y, width, height);

    const label = `${item.label} ${Math.round(item.confidence * 100)}%`;
    const labelWidth = ctx.measureText(label).width + 12;
    const labelY = y >= fontSize + 12 ? y - fontSize - 10 : y;
    ctx.fillStyle = "#0b1619";
    ctx.fillRect(x, labelY, labelWidth, fontSize + 10);
    ctx.fillStyle = "#e8eefb";
    ctx.fillText(label, x + 6, labelY + fontSize + 1);
  }
  badge.textContent = "LAST ANALYZED FRAME · TAP ANALYZE TO REFRESH";
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
  const fontSize = Math.max(13, Math.round(rect.width / 45));
  ctx.font = `600 ${fontSize}px system-ui, sans-serif`;
  ctx.lineWidth = 2;
  for (const item of items.slice(0, 12)) {
    const [x1, y1, x2, y2] = item.box;
    const x = offsetX + x1 * scale;
    const y = offsetY + y1 * scale;
    const track = personTracks.tracks.find((entry) => entry.missed === 0 && entry.item === item);
    const focused = backMode && track?.id === focusedId;
    ctx.strokeStyle = focused ? "#ffcb82" : "#86dcc8";
    ctx.lineWidth = focused ? 4 : 2;
    ctx.strokeRect(x, y, (x2 - x1) * scale, (y2 - y1) * scale);
    const label = track
      ? `person #${track.id} · ${track.motion} · ${Math.round(item.confidence * 100)}%`
      : `${item.label} ${Math.round(item.confidence * 100)}%`;
    const labelY = y >= fontSize + 10 ? y - fontSize - 9 : y;
    const safeLabelY = labelY < 65 ? Math.max(65, y + 6) : labelY;
    ctx.fillStyle = "#0b1619";
    ctx.fillRect(x, safeLabelY, Math.min(ctx.measureText(label).width + 12, rect.width - x), fontSize + 9);
    ctx.fillStyle = "#e8eefb";
    ctx.fillText(label, x + 6, safeLabelY + fontSize, rect.width - x - 12);
  }
}

window.addEventListener("resize", () => {
  if (lastLiveResult) {
    drawLiveDetections(lastLiveResult.items, lastLiveResult.imageWidth, lastLiveResult.imageHeight);
  }
});

async function analyzeFrame(isLive = false) {
  if (!apiBase) {
    setStatus("Set VITE_API_URL to your backend URL before deploying.");
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
    if (isLive) {
      processPersonTracks(items, data.width, data.height);
      drawLiveDetections(items, data.width, data.height);
      if (!backMode) speakLiveResult(items);
    } else {
      drawDetections(items, data.width, data.height);
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
    badge.textContent = "LIVE PREVIEW · NO AUTO UPLOAD";
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

window.addEventListener("pagehide", stopCamera);
