# YT-VDO — Rebuilt Web Edition

An updated Flask + yt-dlp + FFmpeg video downloader for content you own or are authorized to save.

## What changed
- Uses **Deno** as the yt-dlp recommended JavaScript runtime instead of relying on Node runtime configuration.
- Installs `yt-dlp[default]` (including yt-dlp-ejs) at image build time.
- Keeps the existing website design and video+audio validation.
- Adds `/health` to show installed runtime and package versions.
- More useful extraction exceptions in Render logs; public errors do not leak server details.

## Render Docker deployment
1. Push all project files to GitHub repository root.
2. In Render create or update a **Web Service**, choose **Docker** environment.
3. Deploy with **Clear build cache & deploy**.
4. Open `https://YOUR-RENDER-URL/health` and verify Deno, yt-dlp and EJS versions.
5. Analyze a video you own or have permission to download.
6. If extraction still fails, inspect Render Logs; a blocked cloud IP cannot be fixed by installing a different runtime.

## Local run
Install Python 3.12+, FFmpeg and Deno 2.3+ on PATH, then:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Limitations
- Source quality is available only when provided by the platform.
- MP4 and 3GP conversion may be CPU-intensive and may time out on free hosting.
- This project is not guaranteed to work against YouTube restrictions on datacenter IPs.
- Current in-memory job queue and temporary local disk are not suitable for production multi-instance deployment.
- Add authentication, per-IP rate limits, request quotas, monitoring, and stronger isolation before opening to public users.
- This project does not bypass DRM or access private videos.
