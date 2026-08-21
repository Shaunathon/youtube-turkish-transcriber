// Turkish/English hover-linking, click-to-seek on the embedded YouTube
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
