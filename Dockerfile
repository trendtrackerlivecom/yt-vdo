# Node.js is used by yt-dlp for YouTube JavaScript challenges.
FROM node:22-bookworm-slim AS node-runtime

# Build the bgutil PO Token provider server. The bgutil-ytdlp-pot-provider
# plugin (in requirements.txt) runs this server through Node to generate
# the PO Tokens YouTube asks for before returning a player response.
FROM node:22-bookworm-slim AS bgutil-build
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /opt
RUN git clone --depth 1 --branch 2.0.2 https://github.com/Brainicism/bgutil-ytdlp-pot-provider bgutil
WORKDIR /opt/bgutil/server
RUN npm ci --no-audit --no-fund && npx tsc && npm prune --omit=dev --no-audit --no-fund

FROM python:3.12-slim-bookworm
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=bgutil-build /opt/bgutil/server /opt/bgutil/server
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt
COPY . .
RUN mkdir -p downloads && node --version && python -m yt_dlp --version && ffmpeg -version | head -n 1 && test -f /opt/bgutil/server/build/generate_once.js && node /opt/bgutil/server/build/generate_once.js --version
ENV PORT=8000
EXPOSE 8000
CMD ["sh","-c","gunicorn --workers 1 --threads 4 --bind 0.0.0.0:${PORT} --timeout 3600 app:app"]
