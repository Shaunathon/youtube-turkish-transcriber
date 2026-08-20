# Container image for the hosted deployment (see README "Hosting it for
# other people"). Local use doesn't need this - `python3 app.py` is still
# the way to run it on your own machine.
FROM python:3.12-slim

# ffmpeg splits oversized audio into Whisper-sized chunks. Without it,
# any video whose audio exceeds MAX_AUDIO_MB fails outright, so it's a
# hard requirement rather than an optimization.
#
# Deliberately NOT installing Deno / the bgutil PO-token generator: this
# deployment authorizes downloads with a cookies.txt instead, which is
# the more reliable path. If your cookies lapse and you'd rather have the
# token fallback than re-export them, that's the piece to add here.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

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
