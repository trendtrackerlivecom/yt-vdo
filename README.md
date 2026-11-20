# YT-VDO

Flask + yt-dlp + FFmpeg video downloader. Download only videos you own or have permission to download. YouTube access and format availability may change; no guarantee for every video.

## Local run (Windows / Linux / macOS)

1. Install Python 3.12+, FFmpeg, and FFprobe (both must be on PATH).
2. `python -m venv .venv`
3. Activate: Windows `.venv\Scripts\activate` / Linux `source .venv/bin/activate`
4. `pip install -r requirements.txt`
5. `python app.py` and visit http://127.0.0.1:5000

## Docker

`docker build -t yt-vdo .`

`docker run --rm -p 8000:8000 yt-vdo`

Open http://localhost:8000.

## GitHub and online deployment

1. Create a repository named `yt-vdo` at https://github.com/new.
2. Upload the **contents** of this folder (not the ZIP itself).
3. On a Docker-capable hosting service, connect the repository and select Dockerfile deployment. Set port 8000 (or allow the platform to set `PORT`).
4. Use a persistent process and sufficient disk space. Some hosts block YouTube downloads or limit disk/CPU/network. Test with your own permitted video.

## Notes and limitations

- Output MP4 is H.264/AAC, MKV is remuxed if possible, and 3GP is downscaled to 352×288 with H.263/AAC. 3GP is not 4K; its legacy format has low resolution.
- Quality is a *maximum requested source height*, not an upscaling guarantee. Source streams vary.
- Server jobs are kept in process memory; a restart cancels them. Files are deleted after about one hour. For production, add persistent queue, authenticated users, per-user quotas, rate limiting, CSRF protection and dedicated workers. Do not deploy this unprotected as a public unlimited downloader.
- Audio presence is verified with ffprobe; the app fails rather than presenting a silent output as successful.
- This code has not been end-to-end tested against live YouTube in this environment.
