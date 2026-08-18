"""
Everything that talks to YouTube: turning a URL into a video ID, checking
for an existing Turkish transcript, downloading audio when none exists,
and splitting that audio into time-bounded chunks when it's too big for a
single Whisper call.
"""
import json
import logging
import math
import re
import subprocess
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled

from config import FFMPEG_PATH, MAX_AUDIO_MB, SOURCE_LANGUAGE, YT_DLP_COOKIES_BROWSER

log = logging.getLogger("youtube-transcriber")

_ID_RE = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|shorts/|live/))([A-Za-z0-9_-]{11})"
)


def extract_video_id(url: str) -> str:
    match = _ID_RE.search(url)
    if match:
        return match.group(1)
    # Bare 11-char ID pasted directly, with no surrounding URL.
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url.strip()):
        return url.strip()
    raise ValueError(f"Couldn't find a YouTube video ID in: {url}")


class VideoMeta:
    def __init__(self, video_id: str, title: str, duration_seconds: float):
        self.video_id = video_id
        self.title = title
        self.duration_seconds = duration_seconds


def get_video_metadata(video_id: str) -> VideoMeta:
    """Reads title/duration via yt-dlp without downloading anything."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    proc = subprocess.run(
        ["yt-dlp", "--dump-json", "--no-warnings", "--skip-download", url],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp couldn't read video info for {video_id}:\n{proc.stderr.strip()}")
    info = json.loads(proc.stdout)
    return VideoMeta(video_id, info.get("title") or video_id, float(info.get("duration") or 0))


def fetch_existing_transcript(video_id: str) -> Optional[List[dict]]:
    """
    Returns [{"start": float, "end": float, "text": str}, ...] for a
    manually-created Turkish transcript, or None if none exists.

    Deliberately does NOT fall back to YouTube's auto-generated (ASR)
    transcripts: those have no punctuation, inconsistent casing, and are
    generally lower quality than Whisper's own output - a missing manual
    transcript falls through to Whisper instead of using a worse source to
    save an API call.
    """
    api = YouTubeTranscriptApi()
    try:
        transcript_list = api.list(video_id)
    except TranscriptsDisabled:
        return None

    try:
        transcript = transcript_list.find_manually_created_transcript([SOURCE_LANGUAGE])
    except NoTranscriptFound:
        return None

    fetched = transcript.fetch()
    segments = [
        {"start": s.start, "end": s.start + s.duration, "text": s.text.strip()}
        for s in fetched
        if s.text.strip()
    ]
    return segments or None


# Explicit audio-only itags first (confirmed against real YouTube output to
# exist as ordinary https-downloadable formats, unlike the "bestaudio"
# keyword, which was observed resolving inconsistently - sometimes to a
# duplicate the current client can't actually fetch). Falls through to the
# "bestaudio" keyword, then a small muxed video+audio stream, then whatever's
# smallest, in case a different video's format IDs differ.
_FORMAT_SELECTOR = "140/251/139/bestaudio/18/best[height<=360]/worst"


def download_audio(video_id: str, dest_dir: Path) -> Path:
    """
    Downloads the best available audio (audio-only if possible, otherwise a
    small combined video+audio stream - fine for Whisper, which only needs
    the audio track). No re-encoding, no ffmpeg involved in this step.

    YouTube's bot-detection has made a plain, unauthenticated download
    unreliable, so this borrows the configured browser's YouTube session
    cookies first (the fix that's actually worked reliably in testing),
    falling back to an unauthenticated attempt (relying on the bgutil
    PO-token plugin, if installed) in case cookies aren't available.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={video_id}"

    attempts = []
    if YT_DLP_COOKIES_BROWSER:
        attempts.append(["-f", _FORMAT_SELECTOR, "--cookies-from-browser", YT_DLP_COOKIES_BROWSER])
    attempts.append(["-f", _FORMAT_SELECTOR])

    errors = []
    for i, extra_args in enumerate(attempts, 1):
        out_template = str(dest_dir / f"{video_id}-{uuid.uuid4().hex[:8]}.%(ext)s")
        proc = subprocess.run(
            ["yt-dlp", *extra_args, "--no-warnings", "--no-part", "-o", out_template, url],
            capture_output=True, text=True,
        )
        if proc.returncode == 0:
            matches = list(dest_dir.glob(Path(out_template).name.replace("%(ext)s", "*")))
            if matches:
                if i > 1:
                    log.info(f"Audio download succeeded on attempt {i}/{len(attempts)}.")
                return matches[0]
            errors.append(f"attempt {i}: yt-dlp reported success but no output file was found")
        else:
            errors.append(f"attempt {i}: {proc.stderr.strip()}")

    raise RuntimeError(f"yt-dlp couldn't download audio for {video_id} after {len(attempts)} attempts:\n" + "\n---\n".join(errors))


def needs_chunking(audio_path: Path) -> bool:
    size_mb = audio_path.stat().st_size / (1024 * 1024)
    return size_mb > MAX_AUDIO_MB


def split_audio_by_time(audio_path: Path, duration_seconds: float) -> List[Tuple[Path, float, float]]:
    """
    Splits an already-downloaded audio file into roughly-equal, whole-file
    time chunks small enough to fit Whisper's per-request cap. Uses
    ffmpeg's stream copy (-c copy) - no re-encoding, just a remux at each
    cut point - so this is fast and lossless.

    Returns a list of (chunk_path, start_seconds, end_seconds) in order.
    """
    if not FFMPEG_PATH:
        raise RuntimeError(
            "This video's audio is too large for a single Whisper request and needs to be "
            "split, which requires ffmpeg. Install it (e.g. `brew install ffmpeg`) and try again."
        )

    size_mb = audio_path.stat().st_size / (1024 * 1024)
    num_chunks = max(2, math.ceil(size_mb / MAX_AUDIO_MB))
    chunk_duration = duration_seconds / num_chunks

    chunks = []
    for i in range(num_chunks):
        start = i * chunk_duration
        end = duration_seconds if i == num_chunks - 1 else (i + 1) * chunk_duration
        chunk_path = audio_path.with_name(f"{audio_path.stem}-chunk{i + 1}{audio_path.suffix}")
        proc = subprocess.run(
            [
                FFMPEG_PATH, "-y", "-loglevel", "error",
                "-ss", str(start), "-to", str(end),
                "-i", str(audio_path),
                "-c", "copy",
                str(chunk_path),
            ],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed splitting chunk {i + 1}/{num_chunks}:\n{proc.stderr.strip()}")
        chunks.append((chunk_path, start, end))

    log.info(f"Split {audio_path.name} ({size_mb:.1f}MB) into {num_chunks} chunks of ~{chunk_duration / 60:.1f} min each.")
    return chunks


def cleanup(*paths: Path) -> None:
    for p in paths:
        try:
            if p and p.exists():
                p.unlink()
        except OSError:
            log.warning(f"Couldn't remove temporary file {p}")
