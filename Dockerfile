# Container image for the hosted deployment (see README "Hosting it for
# other people"). Local use doesn't need this - `python3 app.py` is still
# the way to run it on your own machine.
FROM python:3.12-slim

# ffmpeg splits oversized audio into Whisper-sized chunks. Without it,
# any video whose audio exceeds MAX_AUDIO_MB fails outright, so it's a
# hard requirement rather than an optimization.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates curl unzip git \
    && rm -rf /var/lib/apt/lists/*

# Deno is NOT optional, despite this deployment authorizing with cookies.
# YouTube gates format resolution behind a JavaScript "n" challenge that
# yt-dlp can only solve with a JS runtime available; without one it fails
# hard - "n challenge solving failed" then "The page needs to be
# reloaded" - for every video, cookies or not. Verified by running yt-dlp
# with deno removed from PATH. Pinned to the version proven working
# against current YouTube rather than floating, so a Deno release can't
# silently change behavior here.
ARG DENO_VERSION=v2.9.4
RUN curl -fsSL "https://github.com/denoland/deno/releases/download/${DENO_VERSION}/deno-x86_64-unknown-linux-gnu.zip" -o /tmp/deno.zip \
    && unzip -q /tmp/deno.zip -d /usr/local/bin \
    && chmod +x /usr/local/bin/deno \
    && rm /tmp/deno.zip \
    && deno --version

# The bgutil PO-token generator, which yt-dlp runs on demand via Deno.
# Best-effort rather than required: when it's missing yt-dlp only warns
# and carries on (unlike the JS runtime above), but the local setup that
# works has it, so match that instead of discovering the difference in
# production. Cloned to $HOME, where the plugin looks by default.
RUN git clone --depth 1 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git \
    /root/bgutil-ytdlp-pot-provider

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Overridden by fly.toml's [env], repeated here so `docker run` locally
# behaves the same way without needing the Fly config.
ENV BIND_HOST=0.0.0.0 \
    PORT=8080 \
    OUTPUT_FOLDER=/data/transcripts \
    COOKIE_SECURE=1

EXPOSE 8080

# Exactly one worker, always. The job queue and its worker thread live in
# this process's memory, so a second worker process would mean a second
# independent queue - two friends could submit work that neither one can
# see the status of. Threads (not workers) handle the concurrent /api/jobs
# polling from every open browser tab.
#
# --timeout 0 disables gunicorn's worker-liveness kill: transcription runs
# for minutes in a background thread, and we'd rather never have a worker
# reaped mid-job than have automatic recovery from a genuine hang.
CMD ["gunicorn", "--workers", "1", "--threads", "8", "--timeout", "0", \
     "--access-logfile", "-", "--bind", "0.0.0.0:8080", "app:app"]
