"""
Central configuration, loaded from environment variables (see .env.example).
"""
import os
import shutil
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Folder where finished HTML reports (and shared assets) are written.
OUTPUT_FOLDER = Path(os.getenv("OUTPUT_FOLDER", "./transcripts")).expanduser().resolve()

# Records OpenAI token usage (prompt/completion/total) for each translation call.
TOKEN_USAGE_LOG = OUTPUT_FOLDER / "token_usage.json"

# OpenAI's hosted Whisper model. Must be "whisper-1" - it's the only
# transcription model that supports response_format="verbose_json" with
# per-segment timestamps, which both [[DEMONSTRATION]] detection and
# click-to-seek depend on.
WHISPER_TRANSCRIBE_MODEL = os.getenv("WHISPER_TRANSCRIBE_MODEL", "whisper-1")

# OpenAI chat model used for translation + vocab/grammar notes.
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Language code used for both youtube-transcript-api lookups and Whisper
# transcription.
SOURCE_LANGUAGE = os.getenv("SOURCE_LANGUAGE", "tr")

# A gap of at least this many seconds between two spoken segments (or
# before the first / after the last) is treated as a wordless passage -
# e.g. playing an instrument - and marked [[DEMONSTRATION]] in the
# transcript.
DEMONSTRATION_GAP_SECONDS = float(os.getenv("DEMONSTRATION_GAP_SECONDS", "7.0"))

# Whisper's API hard-caps a single upload at 25MB. We chunk before hitting
# that, leaving headroom for container/metadata overhead.
MAX_AUDIO_MB = float(os.getenv("MAX_AUDIO_MB", "24"))

# Browser whose YouTube session cookies yt-dlp borrows to authorize audio
# downloads (YouTube's PO-token/bot-detection is unreliable without them).
# Set to "" to disable and rely solely on the bgutil PO-token plugin instead.
YT_DLP_COOKIES_BROWSER = os.getenv("YT_DLP_COOKIES_BROWSER", "chrome")

# Port used to serve transcripts/ locally after a run so the video embed
# actually works (YouTube's embedded player rejects file:// pages). 0 means
# "let the OS pick a free port" if this one's already taken.
SERVE_PORT = int(os.getenv("SERVE_PORT", "8000"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY is not set. Copy .env.example to .env and add your OpenAI API key "
        "(used for both transcription and translation/notes)."
    )

FFMPEG_PATH = shutil.which("ffmpeg")
