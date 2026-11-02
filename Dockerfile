# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ffmpeg: audio extraction / decoding. libsndfile1: librosa I/O.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libsndfile1 ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Deno: yt-dlp needs a JavaScript runtime to solve YouTube's player challenges.
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno

WORKDIR /app
COPY requirements.txt .
# YTDLP_VERSION lets you upgrade yt-dlp with a one-command rebuild:
#   docker compose build --build-arg YTDLP_VERSION=2026.11.01
ARG YTDLP_VERSION=""
RUN pip install -r requirements.txt \
    && if [ -n "$YTDLP_VERSION" ]; then pip install "yt-dlp[default]==$YTDLP_VERSION"; fi

COPY app ./app
COPY scripts ./scripts
# YAMNet audio-event model (16 MB, Apache-2.0), fetched at build time and checked against its pinned SHA-256.
RUN python -c "from app.sources.audio_events import ensure_model; ensure_model()"

RUN useradd --create-home --uid 10001 appuser && mkdir -p /tmp/yt-heatmap && chown appuser /tmp/yt-heatmap
USER appuser

EXPOSE 8000
# Default command runs the API; the worker service overrides it.
CMD ["sh", "-c", "gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY:-2} -b 0.0.0.0:${PORT:-8000} --timeout 60 --access-logfile -"]
