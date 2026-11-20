# Node.js is used by yt-dlp for YouTube JavaScript challenges.
FROM node:22-bookworm-slim AS node-runtime
FROM python:3.12-slim-bookworm
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt
COPY . .
RUN mkdir -p downloads && node --version && python -m yt_dlp --version && ffmpeg -version | head -n 1
ENV PORT=8000
EXPOSE 8000
CMD ["sh","-c","gunicorn --workers 1 --threads 4 --bind 0.0.0.0:${PORT} --timeout 3600 app:app"]
