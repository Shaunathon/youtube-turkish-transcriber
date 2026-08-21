// Renders the transcript list into the sidebar from manifest.js
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
