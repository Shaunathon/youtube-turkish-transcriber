"""
Static shared assets every report page references: styles.css,
sidebar.js, and report.js. Content lives here once and gets rewritten to
disk on every run, so every report page - old or new - reflects the same
up-to-date component instead of baking a copy into each generated file.
"""
from pathlib import Path

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
.sidebar-home-link {
  display: block;
  font-family: 'Work Sans', -apple-system, sans-serif;
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--ink);
  text-decoration: none;
  padding: 7px 10px;
  border-radius: 5px;
  margin-bottom: 10px;
  background: var(--turquoise-soft);
}
.sidebar-home-link:hover { background: var(--turquoise); color: var(--paper); }
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
/* YouTube embed - sticky to the top of the viewport while scrolling the
   transcript below it, so it's always visible without shrinking. */
.video-embed-wrap {
  position: sticky;
  top: 0;
  z-index: 20;
  background: var(--paper);
  padding: 18px 0 14px;
  text-align: center;
}
.video-embed {
  position: relative;
  width: 100%;
  max-width: 640px;
  margin: 0 auto;
  aspect-ratio: 16 / 9;
  background: #111;
  border: 1px solid var(--line);
  border-radius: 4px;
  overflow: hidden;
}
.video-embed iframe { position: absolute; inset: 0; width: 100%; height: 100%; border: 0; }
.autoscroll-toggle {
  margin-top: 8px;
  font-family: 'Work Sans', -apple-system, sans-serif;
  font-size: 0.76rem;
  font-weight: 600;
  border: 1px solid var(--line);
  background: var(--paper);
  color: var(--muted);
  padding: 4px 12px;
  border-radius: 999px;
  cursor: not-allowed;
}
.autoscroll-toggle:not(:disabled) {
  cursor: pointer;
  color: var(--coral);
  border-color: var(--coral);
  background: var(--coral-soft);
}
.autoscroll-toggle:not(:disabled):hover { background: var(--coral); color: var(--paper); }

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
.col.tr p:first-of-type::first-letter {
  font-size: 2.6rem;
  font-weight: 600;
  color: var(--turquoise);
  float: left;
  line-height: 0.8;
  padding: 6px 8px 0 0;
}
/* Each sentence is its own paragraph (not one flowing block) so that
   report.js can independently pad the English side to keep each pair's
   start roughly aligned with its Turkish counterpart - Turkish sentences
   tend to run longer, so left unaddressed the two columns drift apart
   the further into the transcript you read. */
.sent-line { margin: 0 0 0.6em; }
.sent-line:last-child { margin-bottom: 0; }

.sent {
  border-radius: 3px;
  transition: background-color .15s ease, text-decoration-color .15s ease;
}
.sent.seekable { cursor: pointer; text-decoration: underline dotted; text-decoration-color: var(--muted); text-underline-offset: 3px; }
.sent.seekable:hover { text-decoration-color: var(--coral); }
/* Hover pairing (either column) - underline, matches the seekable hint style but solid. */
.sent.sent-active { text-decoration: underline; text-decoration-color: var(--coral); text-decoration-thickness: 2px; text-underline-offset: 3px; }
/* Current video playback position - Turkish side only, driven by report.js polling
   the player's currentTime, independent of hover. */
.col.tr .sent.sent-playing { background: var(--turquoise-soft); }
.sent.marker { font-family: 'Work Sans', -apple-system, sans-serif; font-size: 0.78rem; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); font-style: normal; }

.empty { font-family: 'Work Sans', -apple-system, sans-serif; color: var(--muted); font-size: 0.9rem; font-style: normal; }

.page-footer {
  margin-top: 12px;
  padding-top: 18px;
  border-top: 1px solid var(--line);
}
.page-footer .meta { text-transform: none; letter-spacing: normal; }

/* Home page: the URL-submission form and the live job queue below it. */
.home-form { display: flex; gap: 10px; margin: 24px 0 40px; }
.home-form input[type="url"] {
  flex: 1;
  font-family: 'Work Sans', -apple-system, sans-serif;
  font-size: 1rem;
  padding: 12px 16px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--paper-deep);
  color: var(--ink);
}
.home-form input[type="url"]:focus { outline: 2px solid var(--turquoise); outline-offset: 1px; }
.home-form button {
  font-family: 'Work Sans', -apple-system, sans-serif;
  font-size: 0.95rem;
  font-weight: 600;
  padding: 12px 22px;
  border: none;
  border-radius: 6px;
  background: var(--turquoise);
  color: var(--paper);
  cursor: pointer;
}
.home-form button:hover { background: #23615c; }
.home-form button:disabled { background: var(--muted); cursor: not-allowed; }

.job-list { display: flex; flex-direction: column; gap: 14px; }
.job { border: 1px solid var(--line); border-radius: 6px; padding: 16px 20px; background: var(--paper-deep); }
.job-url { font-family: 'Work Sans', -apple-system, sans-serif; font-size: 0.88rem; color: var(--ink-soft); word-break: break-all; }
.job-status {
  display: inline-block;
  margin-left: 8px;
  padding: 2px 9px;
  border-radius: 999px;
  font-family: 'Work Sans', -apple-system, sans-serif;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.job-status.queued { background: var(--paper); color: var(--muted); border: 1px solid var(--line); }
.job-status.processing { background: var(--turquoise-soft); color: var(--turquoise); }
.job-status.done { background: var(--coral-soft); color: var(--coral); }
.job-status.error { background: #f5d8d8; color: #a83a3a; }
.job-log {
  margin-top: 10px;
  max-height: 220px;
  overflow-y: auto;
  background: var(--ink);
  color: #d9e4f5;
  font-family: 'Work Sans', -apple-system, sans-serif;
  font-size: 0.78rem;
  line-height: 1.5;
  padding: 12px 14px;
  border-radius: 5px;
  white-space: pre-wrap;
}
.job-links a { font-family: 'Work Sans', -apple-system, sans-serif; font-size: 0.85rem; color: var(--coral); text-decoration: none; }
.job-links a:hover { text-decoration: underline; }
.job-error { margin-top: 8px; font-family: 'Work Sans', -apple-system, sans-serif; font-size: 0.88rem; color: #a83a3a; }
.empty-jobs { font-family: 'Work Sans', -apple-system, sans-serif; color: var(--muted); font-size: 0.9rem; }

/* Published-site index (publish.py's docs/index.html). A plain list of
   what's available, since the static site has no submission queue. */
.index-list { list-style: none; padding: 0; margin: 0; }
.index-list li { border-bottom: 1px solid var(--line); }
.index-list li:last-child { border-bottom: none; }
.index-list a {
  display: block;
  padding: 13px 6px;
  font-size: 1.14rem;
  color: var(--ink);
  text-decoration: none;
}
.index-list a:hover { background: var(--turquoise-soft); color: var(--turquoise); }

/* Login page (deployments with APP_PASSWORD set). Narrower than .wrap and
   sidebar-less - it's a single field, and there's no navigation to offer
   someone who isn't signed in yet. */
.login-wrap { max-width: 400px; margin: 0 auto; padding-top: 60px; }
.login-form { display: flex; flex-direction: column; gap: 12px; margin-top: 28px; }
.login-form input[type="password"] {
  font-family: 'Work Sans', -apple-system, sans-serif;
  font-size: 1rem;
  padding: 12px 16px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--paper-deep);
  color: var(--ink);
}
.login-form input[type="password"]:focus { outline: 2px solid var(--turquoise); outline-offset: 1px; }
.login-form button {
  font-family: 'Work Sans', -apple-system, sans-serif;
  font-size: 0.95rem;
  font-weight: 600;
  padding: 12px 22px;
  border: none;
  border-radius: 6px;
  background: var(--turquoise);
  color: var(--paper);
  cursor: pointer;
}
.login-form button:hover { background: #23615c; }
.login-error {
  font-family: 'Work Sans', -apple-system, sans-serif;
  font-size: 0.88rem;
  color: #a83a3a;
  background: #f5d8d8;
  padding: 10px 14px;
  border-radius: 5px;
}

@media (max-width: 720px) {
  .page { flex-direction: column; }
  .sidebar { width: 100%; min-height: auto; position: static; border-right: none; border-bottom: 1px solid var(--line); }
  .sidebar-list { flex-direction: row; flex-wrap: wrap; }
}
@media (max-width: 640px) {
  .columns { grid-template-columns: 1fr; }
  .home-form { flex-direction: column; }
}
"""

SIDEBAR_JS = """// Renders the transcript list into the sidebar from manifest.js
// (regenerated every time a new video finishes processing) by default, or
// from an explicit entries array if one is passed in - the web app's Home
// page uses that to refresh the sidebar live from /api/manifest after a
// job completes, without a full page reload. Exposed on window so it can
// be re-invoked either way.
// The Home link is owned here rather than trusted to each report's baked-in
// markup, because that markup is frozen at generation time: reports built
// before the link existed have none, and ones built before it was made
// relative point at "/" - which on a GitHub Pages project site lands on
// user.github.io instead of user.github.io/<repo>/. Fixing it from this
// shared file corrects every existing report the next time the page loads,
// with no regeneration (and so no repeat API spend).
function ensureHomeLink() {
  var sidebar = document.querySelector('.sidebar');
  if (!sidebar) return;

  var link = sidebar.querySelector('.sidebar-home-link');
  if (!link) {
    link = document.createElement('a');
    link.className = 'sidebar-home-link';
    link.textContent = 'Home';
    // insertBefore with a null reference appends, which is the right
    // outcome if a page somehow has no list to sit above.
    sidebar.insertBefore(link, document.getElementById('sidebar-list'));
  }
  link.setAttribute('href', './');
}

function renderSidebar(entries) {
  ensureHomeLink();

  var container = document.getElementById('sidebar-list');
  if (!container) return;

  var manifest = entries || window.TRANSCRIPT_MANIFEST || [];
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
}
window.renderSidebar = renderSidebar;
renderSidebar();
"""

REPORT_JS = """// Turkish/English hover-linking, click-to-seek on the embedded YouTube
// player, English-column alignment against the Turkish column, and
// playback-position highlighting with autoscroll.

// Turkish sentences tend to run longer than their English translations, so
// left alone the two columns drift apart the deeper into the transcript
// you read. This pads the English side (never the Turkish side) so each
// pair's start stays within about a line and a half of its counterpart.
(function () {
  function alignColumns() {
    var trCol = document.querySelector('.col.tr');
    var enCol = document.querySelector('.col.en');
    if (!trCol || !enCol) return;

    var enLines = enCol.querySelectorAll('.sent-line');
    enLines.forEach(function (el) { el.style.marginTop = ''; });

    var lineHeight = parseFloat(getComputedStyle(enCol).lineHeight) || 24;
    var tolerance = lineHeight * 1.5;

    trCol.querySelectorAll('.sent-line').forEach(function (trLine) {
      var pair = trLine.getAttribute('data-pair');
      var enLine = enCol.querySelector('.sent-line[data-pair="' + pair + '"]');
      if (!enLine) return;
      var diff = trLine.getBoundingClientRect().top - enLine.getBoundingClientRect().top;
      if (diff > tolerance) {
        enLine.style.marginTop = diff + 'px';
      }
    });
  }

  function runWhenFontsReady() {
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(alignColumns);
    } else {
      alignColumns();
    }
  }
  runWhenFontsReady();

  var resizeTimer = null;
  window.addEventListener('resize', function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(alignColumns, 200);
  });
})();

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

// Playback-position highlight + autoscroll. Guarded on there being real
// timestamped Turkish sentence spans (always true in practice, but cheap
// insurance against an edge case like a completely empty transcript).
(function () {
  var trSentences = Array.prototype.slice.call(document.querySelectorAll('.col.tr .sent[data-start]'));
  if (!trSentences.length) return;

  var videoWrap = document.querySelector('.video-embed-wrap');
  var toggleBtn = document.getElementById('autoscroll-toggle');
  var autoScrollEnabled = true;
  var suppressScrollDetection = false;
  var suppressTimeoutId = null;
  var currentEl = null;

  function setAutoScroll(enabled) {
    autoScrollEnabled = enabled;
    if (!toggleBtn) return;
    toggleBtn.disabled = enabled;
    toggleBtn.textContent = enabled ? 'Autoscroll: active' : 'Autoscroll: activate';
  }

  // Computed manually rather than via el.scrollIntoView(): with a
  // position:sticky video pinned over the top of the viewport,
  // scrollIntoView's "nearest visible edge" logic doesn't reliably account
  // for the area the sticky element visually occludes (tested directly -
  // block:'nearest' silently did nothing, block:'center' worked), so this
  // measures both boxes at scroll-time and drives window.scrollTo itself.
  function scrollCurrentIntoView() {
    if (!currentEl) return;
    var margin = 16;
    var videoBottom = videoWrap ? videoWrap.getBoundingClientRect().bottom : 0;
    var rect = currentEl.getBoundingClientRect();
    var delta;
    if (rect.top < videoBottom + margin) {
      delta = rect.top - videoBottom - margin;
    } else if (rect.bottom > window.innerHeight - margin) {
      delta = rect.bottom - window.innerHeight + margin;
    } else {
      return; // already fully visible between the sticky video and the window bottom
    }
    suppressScrollDetection = true;
    window.scrollTo({ top: window.scrollY + delta, behavior: 'smooth' });
    // scrollend is the precise signal and handles this in the normal case.
    // The timeout is only a backstop in case that event doesn't fire for
    // some reason - it needs to be generous, since a long smooth-scroll
    // (e.g. jumping between distant timestamps) can genuinely take a
    // couple of seconds, and firing this before the animation actually
    // finishes would misread its own tail end as a user-initiated scroll.
    clearTimeout(suppressTimeoutId);
    suppressTimeoutId = setTimeout(function () { suppressScrollDetection = false; }, 4000);
  }

  if (toggleBtn) {
    toggleBtn.addEventListener('click', function () {
      setAutoScroll(true);
      scrollCurrentIntoView();
    });
  }

  // Any scroll not caused by our own scrollCurrentIntoView() call means the
  // user took manual control - hand it back to them until they click the
  // button again.
  window.addEventListener('scroll', function () {
    if (suppressScrollDetection) return;
    if (autoScrollEnabled) setAutoScroll(false);
  });
  window.addEventListener('scrollend', function () {
    clearTimeout(suppressTimeoutId);
    suppressScrollDetection = false;
  });

  function tick() {
    if (!window.ytPlayer || typeof window.ytPlayer.getCurrentTime !== 'function') return;
    var t = window.ytPlayer.getCurrentTime();
    var next = null;
    for (var i = 0; i < trSentences.length; i++) {
      var start = parseFloat(trSentences[i].getAttribute('data-start'));
      if (start <= t) { next = trSentences[i]; } else { break; }
    }
    if (next && next !== currentEl) {
      // Skip the scroll (but still highlight) on the very first assignment
      // right after page load - nothing has "changed" yet, so there's
      // nothing to follow, and layout may still be settling (fonts,
      // iframe chrome) which could otherwise produce a spurious scroll.
      var isFirstAssignment = (currentEl === null);
      if (currentEl) currentEl.classList.remove('sent-playing');
      next.classList.add('sent-playing');
      currentEl = next;
      if (autoScrollEnabled && !isFirstAssignment) scrollCurrentIntoView();
    }
  }
  setInterval(tick, 300);
})();
"""

HOME_JS = """// Home page only: submit a YouTube URL to the queue, then poll for
// live progress. Not loaded on report pages - they have nothing to submit.
(function () {
  var form = document.getElementById('home-form');
  var input = document.getElementById('video-url');
  var button = document.getElementById('submit-btn');
  var jobList = document.getElementById('job-list');
  if (!form) return;

  function escapeHtml(s) {
    var div = document.createElement('div');
    div.textContent = s == null ? '' : s;
    return div.innerHTML;
  }

  var STATUS_LABELS = { queued: 'Queued', processing: 'Processing', done: 'Done', error: 'Error' };

  function renderJobs(jobs) {
    if (!jobs.length) {
      jobList.innerHTML = '<p class="empty-jobs">No videos submitted yet.</p>';
      return;
    }
    jobList.innerHTML = jobs.map(function (job) {
      var html = '<div class="job">';
      html += '<span class="job-url">' + escapeHtml(job.url) + '</span>';
      html += '<span class="job-status ' + job.status + '">' + (STATUS_LABELS[job.status] || job.status) + '</span>';
      if (job.status === 'processing' && job.log_lines.length) {
        html += '<div class="job-log">' + escapeHtml(job.log_lines.join('\\n')) + '</div>';
      }
      if (job.status === 'error' && job.error) {
        html += '<div class="job-error">' + escapeHtml(job.error) + '</div>';
      }
      if (job.status === 'done' && job.result_files.length) {
        html += '<div class="job-links">' + job.result_files.map(function (f) {
          return '<a href="' + encodeURI(f) + '">View report: ' + escapeHtml(f) + ' &rarr;</a>';
        }).join('<br>') + '</div>';
      }
      html += '</div>';
      return html;
    }).join('');
  }

  var lastDoneCount = -1;
  function refreshJobs() {
    fetch('/api/jobs')
      .then(function (r) { return r.json(); })
      .then(function (jobs) {
        renderJobs(jobs);
        var doneCount = jobs.filter(function (j) { return j.status === 'done'; }).length;
        if (lastDoneCount !== -1 && doneCount !== lastDoneCount) {
          // A job finished since the last check - the sidebar (built once
          // at page load from manifest.js) is now stale. Refresh it in
          // place from the live manifest rather than reloading the page.
          fetch('/api/manifest')
            .then(function (r) { return r.json(); })
            .then(function (entries) { if (window.renderSidebar) window.renderSidebar(entries); });
        }
        lastDoneCount = doneCount;
      })
      .catch(function () {});
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var url = input.value.trim();
    if (!url) return;
    button.disabled = true;
    fetch('/api/process', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url }),
    })
      .then(function (r) { return r.json(); })
      .then(function () {
        input.value = '';
        refreshJobs();
      })
      .finally(function () { button.disabled = false; });
  });

  refreshJobs();
  setInterval(refreshJobs, 1500);
})();
"""


def write_shared_assets(output_folder: Path) -> None:
    output_folder.mkdir(parents=True, exist_ok=True)
    (output_folder / "styles.css").write_text(CSS, encoding="utf-8")
    (output_folder / "sidebar.js").write_text(SIDEBAR_JS, encoding="utf-8")
    (output_folder / "report.js").write_text(REPORT_JS, encoding="utf-8")
    (output_folder / "home.js").write_text(HOME_JS, encoding="utf-8")
