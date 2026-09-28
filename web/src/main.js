import "./style.css";

const video = document.querySelector("#camera");
const canvas = document.querySelector("#snapshot");
const placeholder = document.querySelector("#camera-placeholder");
const badge = document.querySelector(".badge");
const startButton = document.querySelector("#start");
const analyzeButton = document.querySelector("#analyze");
const stopButton = document.querySelector("#stop");
const status = document.querySelector("#status");
const list = document.querySelector("#observations");
const speakToggle = document.querySelector("#voice");
const apiBase = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

let stream = null;
let busy = false;

function setStatus(message) {
  status.textContent = message;
}

function updateButtons() {
  startButton.disabled = Boolean(stream) || busy;
  analyzeButton.disabled = !stream || busy;
  stopButton.disabled = !stream;
}

function stopCamera() {
  stream?.getTracks().forEach((track) => track.stop());
  stream = null;
  video.srcObject = null;
  placeholder.hidden = false;
  canvas.hidden = true;
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

function captureJpeg() {
  const width = video.videoWidth;
  const height = video.videoHeight;
  if (!width || !height) throw new Error("Camera frame is not ready yet.");
  const scale = Math.min(1, 960 / width, 960 / height);
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
  canvas.hidden = false;
  badge.textContent = "ANALYZING CAPTURED FRAME";
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

analyzeButton.addEventListener("click", async () => {
  if (!apiBase) {
    setStatus("Set VITE_API_URL to your backend URL before deploying.");
    return;
  }
  busy = true;
  updateButtons();
  list.replaceChildren();
  setStatus("Analyzing one frame…");
  try {
    const jpeg = await captureJpeg();
    const response = await fetch(`${apiBase}/v1/analyze`, {
      method: "POST",
      headers: { "Content-Type": "image/jpeg" },
      body: jpeg,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);

    const items = data.observations.sort((a, b) => b.confidence - a.confidence);
    drawDetections(items, data.width, data.height);
    setStatus(items.length
      ? `${items.length} observation(s) · ${data.inference_ms} ms server processing`
      : `No objects found · ${data.inference_ms} ms server processing`);
    for (const item of items.slice(0, 12)) {
      const row = document.createElement("li");
      row.textContent = `${item.label} · ${item.position} (${item.clock} o'clock) · ${Math.round(item.confidence * 100)}%`;
      list.append(row);
    }
    if (speakToggle.checked && items.length && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const first = items[0];
      window.speechSynthesis.speak(new SpeechSynthesisUtterance(
        `${first.label} ${first.position}.`
      ));
    }
  } catch (error) {
    canvas.hidden = true;
    badge.textContent = "LIVE PREVIEW · NO AUTO UPLOAD";
    setStatus(`Analysis failed: ${error.message}`);
  } finally {
    busy = false;
    updateButtons();
  }
});

window.addEventListener("pagehide", stopCamera);
