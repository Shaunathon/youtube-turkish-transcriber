// Renders the transcript list into the sidebar from manifest.js
// (regenerated every time a new video finishes processing) by default, or
// from an explicit entries array if one is passed in - the web app's Home
// page uses that to refresh the sidebar live from /api/manifest after a
// job completes, without a full page reload. Exposed on window so it can
// be re-invoked either way.
function renderSidebar(entries) {
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
