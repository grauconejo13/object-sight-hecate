import "./style.css";

const video = document.querySelector("#camera");
const canvas = document.querySelector("#snapshot");
const overlay = document.querySelector("#overlay");
const placeholder = document.querySelector("#camera-placeholder");
const badge = document.querySelector(".badge");
const startButton = document.querySelector("#start");
const analyzeButton = document.querySelector("#analyze");
const liveButton = document.querySelector("#live");
const stopButton = document.querySelector("#stop");
const status = document.querySelector("#status");
const list = document.querySelector("#observations");
const speakToggle = document.querySelector("#voice");
const apiBase = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

let stream = null;
let busy = false;
let live = false;
let liveTimer = null;
let currentRequest = null;
let lastLiveResult = null;

function setStatus(message) {
  status.textContent = message;
}

function updateButtons() {
  startButton.disabled = Boolean(stream) || busy;
  analyzeButton.disabled = !stream || busy || live;
  liveButton.disabled = !stream;
  liveButton.textContent = live ? "Stop live analysis" : "Start live analysis";
  liveButton.setAttribute("aria-pressed", String(live));
  stopButton.disabled = !stream;
}

function clearOverlay() {
  overlay.getContext("2d").clearRect(0, 0, overlay.width, overlay.height);
  lastLiveResult = null;
}

function stopLiveAnalysis() {
  live = false;
  clearTimeout(liveTimer);
  liveTimer = null;
  currentRequest?.abort();
  currentRequest = null;
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

startButton.addEventListener("click", async () => {
  if (!navigator.mediaDevices?.getUserMedia) {
    setStatus("Camera access needs HTTPS and a supported browser.");
    return;
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: "environment" }, width: { ideal: 960 } },
      audio: false,
    });
    video.srcObject = stream;
    await video.play();
    placeholder.hidden = true;
    canvas.hidden = true;
    clearOverlay();
    badge.textContent = "LIVE PREVIEW · NO AUTO UPLOAD";
    setStatus("Camera ready. Tap Analyze to send one frame.");
  } catch (error) {
    stopCamera();
    setStatus(`Could not start camera: ${error.message}`);
  }
  updateButtons();
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
    ctx.strokeStyle = "#86dcc8";
    ctx.strokeRect(x, y, (x2 - x1) * scale, (y2 - y1) * scale);
    const label = `${item.label} ${Math.round(item.confidence * 100)}%`;
    const labelY = y >= fontSize + 10 ? y - fontSize - 9 : y;
    ctx.fillStyle = "#0b1619";
    ctx.fillRect(x, labelY, ctx.measureText(label).width + 12, fontSize + 9);
    ctx.fillStyle = "#e8eefb";
    ctx.fillText(label, x + 6, labelY + fontSize);
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
      drawLiveDetections(items, data.width, data.height);
    } else {
      drawDetections(items, data.width, data.height);
    }
    setStatus(items.length
      ? `${items.length} observation(s) · ${data.inference_ms} ms server processing`
      : `No objects found · ${data.inference_ms} ms server processing`);
    for (const item of items.slice(0, 12)) {
      const row = document.createElement("li");
      row.textContent = `${item.label} · ${item.position} (${item.clock} o'clock) · ${Math.round(item.confidence * 100)}%`;
      list.append(row);
    }
    if (speakToggle.checked && items.length && "speechSynthesis" in window && !isLive) {
      window.speechSynthesis.cancel();
      const first = items[0];
      window.speechSynthesis.speak(new SpeechSynthesisUtterance(
        `${first.label} ${first.position}.`
      ));
    }
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

window.addEventListener("pagehide", stopCamera);
