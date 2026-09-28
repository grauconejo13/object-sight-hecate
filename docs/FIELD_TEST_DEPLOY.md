# Phone field test: Vercel + Render

This optional path tests the existing Hecate detector outside with a **phone camera**, before connecting the ESP32-S3. A phone browser cannot reach an ESP32 CameraWebServer on your home Wi-Fi once you leave that network. The browser sends one JPEG when you tap **Analyze one frame**; Render runs stateless object detection and returns labels, confidence, and image-relative position. No image database or automatic capture is part of this build.

## Local trial

Use Python 3.11 and Node 20+.

```bash
python -m venv .venv
# Activate your venv (on Windows PowerShell: .\.venv\Scripts\Activate.ps1)
pip install -r requirements-web.txt
uvicorn object_sight_hecate.web_api:app --reload
```

In a second terminal:

```bash
cd web
cp .env.example .env.local
npm install
npm run dev
```

On Windows PowerShell, use `Copy-Item .env.example .env.local`. The browser should open the Vite localhost URL. The first analysis may take longer while the YOLO weights download.

## Render backend

Create a **Python Web Service** from this repository and select the branch containing this feature. Set repository root to the project root.

- Build command: `pip install -r requirements-web.txt`
- Start command: `uvicorn object_sight_hecate.web_api:app --host 0.0.0.0 --port $PORT`
- Environment: `FRONTEND_ORIGINS=https://your-hecate-site.vercel.app`
- Health path: `/health`

The service needs enough memory for PyTorch and Ultralytics. A small or sleeping instance can take a long time on its first request or run out of memory; check Render logs and plan limits before paying for a larger plan. Only one Uvicorn worker is recommended here because every worker would load its own model. Test `https://your-service.onrender.com/health` before trying the frontend.

## Vercel frontend

Import the same repository in Vercel, select this feature branch for a preview, and set:

- Root Directory: `web`
- Framework Preset: Vite
- Build Command: `npm run build`
- Output Directory: `dist`
- Environment Variable: `VITE_API_URL=https://your-service.onrender.com`

After you know the exact Vercel URL, update `FRONTEND_ORIGINS` on Render and redeploy/restart if needed. Preview URLs can change, so use the exact origin you actually test. Vite variables are included in public browser code: put **only the public API URL** there, never an API key. The phone page must be served over HTTPS for camera access.

## Field trial

1. On the phone, open the Vercel HTTPS URL and grant camera permission.
2. Start camera, point it at a consenting test scene, and tap **Analyze one frame**.
3. Compare labels and left/center/right positions with what you see. Turn on **Speak the first result** to try browser speech synthesis.
4. Stop the camera when finished. Capture and processing times can vary with mobile connection, Render cold starts, and CPU inference.

This is a manual remote preview, **not** a continuous safety warning system. The API has no account system or rate limiting, so keep its URL within your test group and monitor usage; CORS controls browser access but is not authentication. Do not submit imagery of bystanders without considering their privacy. Avoid treating a missing detection as evidence that a path is clear.

This path is separate from the competition's AWS requirement: the final OpenCV AI Competition entry still needs a meaningful component running on AWS. Later, ESP32 frames can be consumed on the laptop over local Wi-Fi or sent outward through a deliberate, authenticated relay; directly exposing the camera's port is not part of this setup.
