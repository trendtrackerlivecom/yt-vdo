# Deno is recommended by yt-dlp for YouTube EJS challenge solving.
FROM denoland/deno:bin-2.6.8 AS deno
FROM python:3.12-slim
COPY --from=deno /deno /usr/local/bin/deno
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p downloads && python -m compileall -q app.py && deno --version && python -m yt_dlp --version
ENV PYTHONUNBUFFERED=1
EXPOSE 10000
CMD ["sh", "-c", "exec gunicorn -b 0.0.0.0:${PORT:-10000} --workers 1 --threads 4 --timeout 120 app:app"]
