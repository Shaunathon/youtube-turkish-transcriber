"""
Builds the side-by-side HTML transcript reports, plus the shared assets
they all reference: styles.css, sidebar.js, report.js, and manifest.js.

Each report.html is just markup; the sidebar, styling, and interactivity
live in the shared files so every page reflects the same up-to-date
component instead of baking a copy into every generated file.
"""
import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from demonstration import DEMONSTRATION_TOKEN

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;1,500&family=Work+Sans:wght@400;500;600&display=swap');

:root {
  --paper: #f6efe1;
  --paper-deep: #efe4ce;
  --ink: #1e2b45;
  --ink-soft: #4a5872;
  --turquoise: #2c7873;
  --turquoise-soft: #e4efec;
  --coral: #b84b32;
  --coral-soft: #f5e3da;
  --line: #ded0ae;
  --muted: #8a7f6a;
  --sidebar-width: 240px;
}
* { box-sizing: border-box; }
html, body { margin: 0; }
body {
  background: var(--paper);
  color: var(--ink);
  font-family: 'Cormorant Garamond', Georgia, serif;
  line-height: 1.65;
}

.page { display: flex; align-items: flex-start; min-height: 100vh; }
.sidebar {
  width: var(--sidebar-width);
  flex-shrink: 0;
  background: var(--paper-deep);
  border-right: 1px solid var(--line);
  min-height: 100vh;
  padding: 26px 20px;
  position: sticky;
  top: 0;
}
.sidebar-title {
  font-family: 'Work Sans', -apple-system, sans-serif;
  text-transform: uppercase;
  font-size: 0.72rem;
  letter-spacing: 0.1em;
  font-weight: 600;
  color: var(--muted);
  margin-bottom: 16px;
}
.sidebar-list { display: flex; flex-direction: column; gap: 2px; }
.sidebar-list a {
  font-family: 'Work Sans', -apple-system, sans-serif;
  font-size: 0.88rem;
  color: var(--ink-soft);
  text-decoration: none;
  padding: 7px 10px;
  border-radius: 5px;
  line-height: 1.3;
}
.sidebar-list a:hover { background: var(--turquoise-soft); color: var(--ink); }
.sidebar-list a.active { background: var(--turquoise); color: var(--paper); font-weight: 600; }
.sidebar-empty {
  font-family: 'Work Sans', -apple-system, sans-serif;
  font-size: 0.82rem;
  color: var(--muted);
}

.content { flex: 1; min-width: 0; padding: 0 20px 72px; }

.ornament-rule {
  height: 9px;
  margin: 0 -20px 0;
  background: repeating-linear-gradient(
    135deg,
    var(--turquoise), var(--turquoise) 7px,
    var(--coral) 7px, var(--coral) 9px,
    var(--paper) 9px, var(--paper) 17px
  );
}
.wrap { max-width: 900px; margin: 0 auto; }
header { padding: 26px 4px 20px; border-bottom: 1px solid var(--line); margin-bottom: 34px; }
h1 { font-size: 1.9rem; font-weight: 600; margin: 0 0 6px; color: var(--ink); }
.meta {
  font-family: 'Work Sans', -apple-system, sans-serif;
  font-size: 0.78rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--muted);
}
.badge {
  display: inline-block;
  margin-left: 8px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--turquoise-soft);
  color: var(--turquoise);
  font-weight: 600;
  letter-spacing: 0.03em;
}

/* YouTube embed */
.video-embed-wrap { margin-top: 18px; }
.video-embed {
  position: relative;
  width: 100%;
  max-width: 640px;
  aspect-ratio: 16 / 9;
  background: #111;
  border: 1px solid var(--line);
  border-radius: 4px;
  overflow: hidden;
}
.video-embed iframe { position: absolute; inset: 0; width: 100%; height: 100%; border: 0; }
.watch-on-youtube {
  display: inline-block;
  margin-top: 8px;
  font-family: 'Work Sans', -apple-system, sans-serif;
  font-size: 0.8rem;
  color: var(--coral);
  text-decoration: none;
}
.watch-on-youtube:hover { text-decoration: underline; }

.columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border: 1px solid var(--line);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 44px;
  background: var(--line);
  gap: 1px;
}
.col { padding: 30px 32px; background: var(--paper); }
.col.en { background: #fbf7ee; }
.col-label {
  font-family: 'Work Sans', -apple-system, sans-serif;
  text-transform: uppercase;
  font-size: 0.72rem;
  letter-spacing: 0.1em;
  font-weight: 600;
  margin-bottom: 14px;
}
.col.tr .col-label { color: var(--turquoise); }
.col.en .col-label { color: var(--ink-soft); }
.col p { margin: 0; font-size: 1.18rem; }
.col.tr p::first-letter {
  font-size: 2.6rem;
  font-weight: 600;
  color: var(--turquoise);
  float: left;
  line-height: 0.8;
  padding: 6px 8px 0 0;
}

.sent { border-radius: 3px; transition: background-color .15s ease, text-decoration-color .15s ease; }
.col.tr .sent.sent-active { background: var(--turquoise-soft); }
.col.en .sent.sent-active { text-decoration: underline; text-decoration-color: var(--coral); text-decoration-thickness: 2px; text-underline-offset: 3px; }
.sent.seekable { cursor: pointer; text-decoration: underline dotted; text-decoration-color: var(--muted); text-underline-offset: 3px; }
.sent.seekable:hover { text-decoration-color: var(--coral); }
.sent.marker { font-family: 'Work Sans', -apple-system, sans-serif; font-size: 0.78rem; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); font-style: normal; }

h2 {
  font-family: 'Work Sans', -apple-system, sans-serif;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
  color: var(--coral);
  border-bottom: 1px solid var(--line);
  padding-bottom: 10px;
  margin: 0 0 18px;
}
section { margin-bottom: 44px; }
table { width: 100%; border-collapse: collapse; font-family: 'Work Sans', -apple-system, sans-serif; font-size: 0.94rem; }
th {
  text-align: left;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 600;
  color: var(--muted);
  padding: 8px 12px;
  background: var(--paper-deep);
}
td { padding: 10px 12px; border-bottom: 1px solid var(--line); vertical-align: top; }
tr:last-child td { border-bottom: none; }
.tr-word { font-family: 'Cormorant Garamond', Georgia, serif; font-weight: 600; font-size: 1.08rem; white-space: nowrap; color: var(--ink); }
.note { color: var(--muted); font-size: 0.86rem; }
.grammar-item {
  border-left: 3px solid var(--coral);
  background: var(--coral-soft);
  padding: 14px 20px;
  margin-bottom: 12px;
  border-radius: 0 4px 4px 0;
}
.grammar-topic { font-family: 'Work Sans', -apple-system, sans-serif; font-weight: 600; font-size: 0.9rem; color: var(--ink); margin-bottom: 4px; }
.grammar-explanation { font-size: 1.02rem; color: var(--ink-soft); }
.empty { font-family: 'Work Sans', -apple-system, sans-serif; color: var(--muted); font-size: 0.9rem; font-style: normal; }

@media (max-width: 720px) {
  .page { flex-direction: column; }
  .sidebar { width: 100%; min-height: auto; position: static; border-right: none; border-bottom: 1px solid var(--line); }
  .sidebar-list { flex-direction: row; flex-wrap: wrap; }
}
@media (max-width: 640px) {
  .columns { grid-template-columns: 1fr; }
}
"""

SIDEBAR_JS = """// Renders the transcript list into the sidebar from manifest.js,
// which main.py regenerates every time a new video is processed.
(function () {
  var container = document.getElementById('sidebar-list');
  if (!container) return;

  var manifest = window.TRANSCRIPT_MANIFEST || [];
  var currentFile = decodeURIComponent(window.location.pathname.split('/').pop());
  if (currentFile === '' || currentFile === 'index.html') {
    currentFile = manifest.length ? manifest[0].file : currentFile;
  }

  if (manifest.length === 0) {
    container.innerHTML = '<div class="sidebar-empty">No transcripts yet.</div>';
    return;
  }

  container.innerHTML = '';
  manifest.forEach(function (entry) {
    var link = document.createElement('a');
    link.href = entry.file;
    link.textContent = entry.title;
    if (entry.file === currentFile) {
      link.classList.add('active');
    }
    container.appendChild(link);
  });
})();
"""

REPORT_JS = """// Turkish/English hover-linking, plus click-to-seek on the embedded
// YouTube player when a report was built with --click-to-seek (sentence
// spans then carry a data-start attribute). No-ops quietly otherwise.
window.onYouTubeIframeAPIReady = function () {
  var el = document.getElementById('yt-player');
  if (el && window.YT) {
    window.ytPlayer = new YT.Player('yt-player');
  }
};

(function () {
  var sentences = document.querySelectorAll('.sent');
  sentences.forEach(function (el) {
    var pair = el.getAttribute('data-pair');
    var group = document.querySelectorAll('.sent[data-pair="' + pair + '"]');
    el.addEventListener('mouseenter', function () {
      group.forEach(function (e) { e.classList.add('sent-active'); });
    });
    el.addEventListener('mouseleave', function () {
      group.forEach(function (e) { e.classList.remove('sent-active'); });
    });

    var start = el.getAttribute('data-start');
    if (start !== null) {
      el.classList.add('seekable');
      el.addEventListener('click', function () {
        if (window.ytPlayer && typeof window.ytPlayer.seekTo === 'function') {
          window.ytPlayer.seekTo(parseFloat(start), true);
          window.ytPlayer.playVideo();
        }
      });
    }
  });
})();
"""


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


def _sentence_spans(pairs: list, lang_key: str) -> str:
    spans = []
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
        spans.append(f'<span {attrs}>{text}</span>')
    return " ".join(spans)


def write_shared_assets(output_folder: Path) -> None:
    output_folder.mkdir(parents=True, exist_ok=True)
    (output_folder / "styles.css").write_text(CSS, encoding="utf-8")
    (output_folder / "sidebar.js").write_text(SIDEBAR_JS, encoding="utf-8")
    (output_folder / "report.js").write_text(REPORT_JS, encoding="utf-8")


def update_manifest(output_folder: Path) -> None:
    entries = []
    for report_path in output_folder.glob("*.html"):
        if report_path.stem == "index":
            continue
        entries.append({"file": report_path.name, "title": report_path.stem.replace("-", " "), "mtime": report_path.stat().st_mtime})
    entries.sort(key=lambda e: (e["mtime"], e["file"]), reverse=True)
    for e in entries:
        del e["mtime"]

    manifest_js = "window.TRANSCRIPT_MANIFEST = " + json.dumps(entries, ensure_ascii=False, indent=2) + ";\n"
    output_folder.mkdir(parents=True, exist_ok=True)
    (output_folder / "manifest.js").write_text(manifest_js, encoding="utf-8")


def report_stem(video_title: str, click_to_seek: bool, part: Optional[int]) -> str:
    stem = slugify(video_title)
    if click_to_seek:
        stem += "-clicktoseek"
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
    click_to_seek: bool,
    result: dict,
    output_folder: Path,
) -> Path:
    sentence_pairs = result.get("sentence_pairs", [])
    vocabulary = result.get("vocabulary", [])
    grammar_notes = result.get("grammar_notes", [])

    if sentence_pairs:
        tr_html = f'<p>{_sentence_spans(sentence_pairs, "turkish")}</p>'
        en_html = f'<p>{_sentence_spans(sentence_pairs, "english")}</p>'
    else:
        tr_html = '<p class="empty">No transcript available for this clip.</p>'
        en_html = '<p class="empty">Translation unavailable for this clip.</p>'

    if vocabulary:
        vocab_rows = "\n".join(
            f"""      <tr>
        <td class="tr-word">{_esc(v.get('turkish', ''))}</td>
        <td>{_esc(v.get('english', ''))}</td>
        <td class="note">{_esc(v.get('note', ''))}</td>
      </tr>"""
            for v in vocabulary
        )
        vocab_html = f"""<table>
      <tr><th>Turkish</th><th>English</th><th>Note</th></tr>
{vocab_rows}
    </table>"""
    else:
        vocab_html = '<p class="empty">No standout vocabulary flagged for this clip.</p>'

    if grammar_notes:
        grammar_html = "\n".join(
            f"""    <div class="grammar-item">
      <div class="grammar-topic">{_esc(g.get('topic', ''))}</div>
      <div class="grammar-explanation">{_esc(g.get('explanation', ''))}</div>
    </div>"""
            for g in grammar_notes
        )
    else:
        grammar_html = '<p class="empty">No specific grammar points flagged for this clip.</p>'

    embed_src = f"https://www.youtube.com/embed/{video_id}?enablejsapi=1&start={int(embed_start)}"
    if embed_end:
        embed_src += f"&end={int(embed_end)}"
    watch_url = f"https://www.youtube.com/watch?v={video_id}&t={int(embed_start)}s"
    video_html = f"""    <div class="video-embed-wrap">
      <div class="video-embed">
        <iframe id="yt-player" src="{html.escape(embed_src)}" title="{_esc(video_title)}"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowfullscreen></iframe>
      </div>
      <a class="watch-on-youtube" href="{html.escape(watch_url)}" target="_blank" rel="noopener noreferrer">Watch on YouTube &#8599;</a>
    </div>
"""

    display_title = video_title
    if part:
        display_title += f" — Part {part}" + (f" of {total_parts}" if total_parts else "")

    timestamp = datetime.now().strftime("%B %d, %Y · %I:%M %p")
    mode_badge = "click-to-seek" if click_to_seek else "freeform"
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
  <nav class="sidebar">
    <div class="sidebar-title">Transcripts</div>
    <div class="sidebar-list" id="sidebar-list">Loading&hellip;</div>
  </nav>
  <div class="content">
    <div class="ornament-rule"></div>
    <div class="wrap">
      <header>
        <h1>{title}</h1>
        <div class="meta">Turkish video transcript &amp; notes &middot; {timestamp} &middot; {html.escape(transcript_source)}<span class="badge">{mode_badge}</span></div>
{video_html}      </header>

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

      <section>
        <h2>Vocabulary</h2>
        {vocab_html}
      </section>

      <section>
        <h2>Grammar notes</h2>
{grammar_html}
      </section>
    </div>
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
    stem = report_stem(video_title, click_to_seek, part)
    out_path = output_folder / f"{stem}.html"
    out_path.write_text(doc, encoding="utf-8")
    return out_path
