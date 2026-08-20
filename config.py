"""
Central configuration, loaded from environment variables (see .env.example).
"""
import base64
import os
import secrets
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

# Path to an exported cookies.txt, tried ahead of YT_DLP_COOKIES_BROWSER.
# This is the only cookie source that works on a server: there's no browser
# profile there to borrow a session from.
YT_DLP_COOKIES_FILE = os.getenv("YT_DLP_COOKIES_FILE", "")

# Hosting platforms hand you environment variables, not files, so a
# deployment ships its cookies.txt base64-encoded in YT_COOKIES_B64 and we
# materialize it here. Written 0600 and never logged - it's a live YouTube
# session, and anything that can read it can act as your account.
_cookies_b64 = os.getenv("YT_COOKIES_B64", "")
if _cookies_b64 and not YT_DLP_COOKIES_FILE:
    _cookie_path = Path(os.getenv("YT_COOKIES_PATH", "/tmp/yt-cookies.txt"))
    _cookie_path.parent.mkdir(parents=True, exist_ok=True)
    _cookie_path.write_bytes(base64.b64decode(_cookies_b64))
    _cookie_path.chmod(0o600)
    YT_DLP_COOKIES_FILE = str(_cookie_path)

# Port used to serve transcripts/ locally after a run so the video embed
# actually works (YouTube's embedded player rejects file:// pages). 0 means
# "let the OS pick a free port" if this one's already taken. Hosting
# platforms dictate the port via $PORT, which takes precedence.
SERVE_PORT = int(os.getenv("PORT") or os.getenv("SERVE_PORT", "8000"))

# Interface app.py binds to. 127.0.0.1 keeps the app reachable only from
# this machine, which is what you want locally; a container needs 0.0.0.0
# so traffic from outside it can get in.
BIND_HOST = os.getenv("BIND_HOST", "127.0.0.1")

# Shared password gating the web app. Empty means no authentication at
# all - the right default for a local-only run, and the reason this must
# be set for any deployment reachable beyond your own machine: without it,
# anyone who finds the URL can queue jobs against your OpenAI key.
APP_PASSWORD = os.getenv("APP_PASSWORD", "")

# Signs the login session cookie. A stable value keeps people logged in
# across restarts and deploys; without one we generate a random key per
# process, which is secure but logs everyone out whenever the app restarts.
SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)

# Marks the session cookie Secure (HTTPS-only). Set this wherever the app
# is served over HTTPS; leave it off locally, where http://127.0.0.1 would
# otherwise never be able to hold a session.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "") == "1"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY is not set. Copy .env.example to .env and add your OpenAI API key "
        "(used for both transcription and translation/notes)."
    )

FFMPEG_PATH = shutil.which("ffmpeg")
