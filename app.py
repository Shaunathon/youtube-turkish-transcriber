"""
Persistent web app entry point: a "Home" page to paste YouTube URLs into
(queued and processed one at a time, with live status), plus every
generated report served alongside it in the sidebar. This is the
recommended way to run the tool day-to-day; main.py's CLI still works
unchanged for scripting several videos back to back (`--no-serve`).

Run with:  python3 app.py
"""
import logging
import threading
import webbrowser

from flask import Flask, jsonify, request, send_from_directory

from assets import write_shared_assets
from config import OUTPUT_FOLDER, SERVE_PORT
from jobs import JobQueue
from report_builder import build_home_page, manifest_entries, update_manifest

log = logging.getLogger("youtube-transcriber")

# The Home page polls /api/jobs every 1.5s to show live status, and
# Flask's dev server logs every request at INFO by default - left alone
# that floods the terminal with routine polling noise. Errors (5xx) still
# come through at their own level, so real problems aren't hidden.
logging.getLogger("werkzeug").setLevel(logging.WARNING)

app = Flask(__name__)
job_queue = JobQueue()


@app.after_request
def no_cache(response):
    # Same reasoning as serve.py's _NoCacheHandler: this is a local,
    # single-user server writing fresh files on every run, and browsers'
    # default heuristic caching has previously served stale styles.css/
    # report.js across separate runs on the same port.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
def home():
    return build_home_page()


@app.route("/api/process", methods=["POST"])
def api_process():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "url is required"}), 400
    job = job_queue.submit(url)
    return jsonify(job.to_dict())


@app.route("/api/jobs")
def api_jobs():
    return jsonify([job.to_dict() for job in job_queue.list_jobs()])


@app.route("/api/manifest")
def api_manifest():
    return jsonify(manifest_entries(OUTPUT_FOLDER))


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, max_age=0)


def main() -> None:
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    write_shared_assets(OUTPUT_FOLDER)
    update_manifest(OUTPUT_FOLDER)

    url = f"http://127.0.0.1:{SERVE_PORT}/"
    log.info(f"Serving at {url} - press Ctrl+C to stop.")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=SERVE_PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
