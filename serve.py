"""
Serves transcripts/ over local HTTP and opens the freshest report in the
default browser. YouTube's embedded player rejects file:// pages (you get a
player error instead of the video), so "double-click the HTML file" doesn't
work here the way it did for the old audio-player-based reports - this
makes "run it, see it" the actual default instead of an undocumented manual
follow-up step.
"""
import logging
import socketserver
import threading
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler
from pathlib import Path

log = logging.getLogger("youtube-transcriber")


class _ReusableServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class _NoCacheHandler(SimpleHTTPRequestHandler):
    """
    Plain SimpleHTTPRequestHandler sends no cache-control headers, so
    browsers apply their own heuristic caching to shared assets like
    styles.css/report.js - across separate runs of this tool on the same
    port, that can silently serve a stale cached copy instead of the
    freshly regenerated one. Nothing here benefits from caching (it's a
    local, single-user, freshly-written-to-disk server), so disable it.
    """

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        super().end_headers()


def serve_and_open(output_folder: Path, open_path: Path, preferred_port: int) -> None:
    """Blocks until Ctrl+C. Safe to call even if preferred_port is busy."""
    handler = partial(_NoCacheHandler, directory=str(output_folder))
    try:
        httpd = _ReusableServer(("127.0.0.1", preferred_port), handler)
    except OSError:
        httpd = _ReusableServer(("127.0.0.1", 0), handler)

    port = httpd.server_address[1]
    url = f"http://127.0.0.1:{port}/{open_path.name}"

    log.info(f"Serving {output_folder} at http://127.0.0.1:{port}/")
    log.info(f"Opening {url} in your browser - press Ctrl+C here when you're done viewing.")
    threading.Timer(0.3, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("Stopping server.")
    finally:
        httpd.server_close()
