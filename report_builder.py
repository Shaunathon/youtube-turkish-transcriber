"""
Builds each report.html doc and the manifest.js sidebar listing all of
them. Markup only - styling and interactivity live in assets.py's shared
files so every page reflects the same up-to-date component instead of
baking a copy into every generated file.
"""
import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from demonstration import DEMONSTRATION_TOKEN


def _esc(text: str) -> str:
    return html.escape(text or "").replace("\n", "<br>")


_TR_TRANSLITERATE = str.maketrans({
    "ı": "i", "İ": "I", "ş": "s", "Ş": "S", "ç": "c", "Ç": "C",
    "ğ": "g", "Ğ": "G", "ö": "o", "Ö": "O", "ü": "u", "Ü": "U",
})


def slugify(text: str) -> str:
    text = text.translate(_TR_TRANSLITERATE)
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")
    return text or "video"


def _sentence_lines(pairs: list, lang_key: str) -> str:
    """
    One <p class="sent-line" data-pair="i"> per sentence, rather than one
    shared paragraph - report.js needs each sentence individually
    positioned to measure and align the English side against the Turkish
    side. data-pair is on both the paragraph (used for alignment) and the
    inner span (used for hover-pairing/click-to-seek, unchanged).
    """
    lines = []
    for i, p in enumerate(pairs):
        text = _esc(p.get(lang_key, ""))
        if not text:
            continue
        classes = "sent"
        if p.get("turkish") == DEMONSTRATION_TOKEN:
            classes += " marker"
        attrs = f'class="{classes}" data-pair="{i}"'
        if "start" in p:
            attrs += f' data-start="{p["start"]:.2f}"'
        lines.append(f'<p class="sent-line" data-pair="{i}"><span {attrs}>{text}</span></p>')
    return "\n          ".join(lines)


def manifest_entries(output_folder: Path) -> list:
    """[{"file", "title"}, ...] for every report in output_folder, newest
    first. Recomputed fresh from disk each call (a cheap glob), so unlike
    the static manifest.js file this is always current - used by app.py's
    /api/manifest for the web UI to refresh its sidebar without a reload."""
    entries = []
    for report_path in output_folder.glob("*.html"):
        if report_path.stem == "index":
            continue
        entries.append({"file": report_path.name, "title": report_path.stem.replace("-", " "), "mtime": report_path.stat().st_mtime})
    entries.sort(key=lambda e: (e["mtime"], e["file"]), reverse=True)
    for e in entries:
        del e["mtime"]
    return entries


def update_manifest(output_folder: Path) -> None:
    manifest_js = "window.TRANSCRIPT_MANIFEST = " + json.dumps(manifest_entries(output_folder), ensure_ascii=False, indent=2) + ";\n"
    output_folder.mkdir(parents=True, exist_ok=True)
    (output_folder / "manifest.js").write_text(manifest_js, encoding="utf-8")


def _sidebar_html() -> str:
    return """  <nav class="sidebar">
    <div class="sidebar-title">Transcripts</div>
    <a class="sidebar-home-link" href="/">Home</a>
    <div class="sidebar-list" id="sidebar-list">Loading&hellip;</div>
  </nav>"""


def report_stem(video_title: str, part: Optional[int]) -> str:
    stem = slugify(video_title)
    if part:
        stem += f"-part-{part}"
    return stem


def build_html_report(
    video_title: str,
    video_id: str,
    embed_start: float,
    embed_end: Optional[float],
    part: Optional[int],
    total_parts: Optional[int],
    transcript_source: str,
    result: dict,
    output_folder: Path,
    token_usage: Optional[dict] = None,
) -> Path:
    sentence_pairs = result.get("sentence_pairs", [])

    if sentence_pairs:
        tr_html = _sentence_lines(sentence_pairs, "turkish")
        en_html = _sentence_lines(sentence_pairs, "english")
    else:
        tr_html = '<p class="empty">No transcript available for this clip.</p>'
        en_html = '<p class="empty">Translation unavailable for this clip.</p>'

    if token_usage and token_usage.get("total_tokens"):
        footer_html = f"""    <footer class="page-footer">
      <div class="meta">Token usage this run: {token_usage['total_tokens']:,} total ({token_usage.get('prompt_tokens', 0):,} prompt + {token_usage.get('completion_tokens', 0):,} completion)</div>
    </footer>
"""
    else:
        footer_html = ""

    # No "Watch on YouTube" link - the embed itself already shows one, both
    # normally (in the player's own chrome) and as the fallback message
    # when a video has embedding disabled, so a second one here was redundant.
    embed_src = f"https://www.youtube.com/embed/{video_id}?enablejsapi=1&start={int(embed_start)}"
    if embed_end:
        embed_src += f"&end={int(embed_end)}"
    video_html = f"""  <div class="video-embed-wrap">
    <div class="video-embed">
      <iframe id="yt-player" src="{html.escape(embed_src)}" title="{_esc(video_title)}"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowfullscreen></iframe>
    </div>
    <button type="button" id="autoscroll-toggle" class="autoscroll-toggle" disabled>Autoscroll: active</button>
  </div>
"""

    display_title = video_title
    if part:
        display_title += f" — Part {part}" + (f" of {total_parts}" if total_parts else "")

    timestamp = datetime.now().strftime("%B %d, %Y · %I:%M %p")
    title = html.escape(display_title)

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Turkish video transcript</title>
<link rel="stylesheet" href="styles.css">
</head>
<body>
<div class="page">
{_sidebar_html()}
  <div class="content">
    <div class="ornament-rule"></div>
    <div class="wrap">
      <header>
        <h1>{title}</h1>
        <div class="meta">Turkish video transcript &middot; {timestamp} &middot; {html.escape(transcript_source)}</div>
      </header>
{video_html}
      <div class="columns">
        <div class="col tr">
          <div class="col-label">Türkçe</div>
          {tr_html}
        </div>
        <div class="col en">
          <div class="col-label">English</div>
          {en_html}
        </div>
      </div>
{footer_html}    </div>
  </div>
</div>
<script src="manifest.js"></script>
<script src="sidebar.js" defer></script>
<script src="report.js"></script>
<script src="https://www.youtube.com/iframe_api"></script>
</body>
</html>
"""

    output_folder.mkdir(parents=True, exist_ok=True)
    stem = report_stem(video_title, part)
    out_path = output_folder / f"{stem}.html"
    out_path.write_text(doc, encoding="utf-8")
    return out_path


def build_login_page(error: Optional[str] = None) -> str:
    """
    The shared-password gate (app.py's `/login`), shown only when
    APP_PASSWORD is configured.

    Deliberately renders without the sidebar: it lists every transcript's
    title, and those shouldn't be readable by someone who hasn't gotten
    past this page yet.
    """
    error_html = f'\n          <div class="login-error">{_esc(error)}</div>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign in — Turkish video transcripts</title>
<link rel="stylesheet" href="/styles.css">
</head>
<body>
<div class="page">
  <div class="content">
    <div class="ornament-rule"></div>
    <div class="login-wrap">
      <header>
        <h1>Turkish video transcripts</h1>
        <div class="meta">Enter the shared password to continue</div>
      </header>
      <form class="login-form" method="post">
        <input type="password" name="password" placeholder="Password" autofocus required>
        <button type="submit">Sign in</button>{error_html}
      </form>
    </div>
  </div>
</div>
</body>
</html>
"""


def build_home_page() -> str:
    """
    The web app's landing page (app.py's `GET /`): paste a URL, watch it
    process. Returned as a string rather than written to disk - app.py
    serves it directly, it's not a static report.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Home — Turkish video transcripts</title>
<link rel="stylesheet" href="styles.css">
</head>
<body>
<div class="page">
{_sidebar_html()}
  <div class="content">
    <div class="ornament-rule"></div>
    <div class="wrap">
      <header>
        <h1>Add a video</h1>
        <div class="meta">Paste a YouTube link below to transcribe and translate it</div>
      </header>

      <form id="home-form" class="home-form">
        <input type="url" id="video-url" placeholder="https://www.youtube.com/watch?v=..." required>
        <button type="submit" id="submit-btn">Start</button>
      </form>

      <section>
        <h2>Queue</h2>
        <div id="job-list" class="job-list"><p class="empty-jobs">Loading&hellip;</p></div>
      </section>
    </div>
  </div>
</div>
<script src="manifest.js"></script>
<script src="sidebar.js" defer></script>
<script src="home.js" defer></script>
</body>
</html>
"""
