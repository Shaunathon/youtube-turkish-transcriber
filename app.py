"""
Persistent web app entry point: a "Home" page to paste YouTube URLs into
(queued and processed one at a time, with live status), plus every
generated report served alongside it in the sidebar. This is the
recommended way to run the tool day-to-day; main.py's CLI still works
unchanged for scripting several videos back to back (`--no-serve`).

Run locally with:  python3 app.py
Deployed, it runs under gunicorn instead (see Dockerfile) - so everything
needed at startup happens at import time, not inside main().
"""
import logging
import secrets
import threading
import webbrowser
from datetime import timedelta

from flask import (
    Flask,
    jsonify,
    redirect,
    request,
    send_from_directory,
    session,
    url_for,
)

from assets import write_shared_assets
from config import (
    APP_PASSWORD,
    BIND_HOST,
    COOKIE_SECURE,
    OUTPUT_FOLDER,
    SECRET_KEY,
    SERVE_PORT,
)
from jobs import JobQueue
from report_builder import (
    build_home_page,
    build_login_page,
    manifest_entries,
    update_manifest,
)

log = logging.getLogger("youtube-transcriber")

# The Home page polls /api/jobs every 1.5s to show live status, and
# Flask's dev server logs every request at INFO by default - left alone
# that floods the terminal with routine polling noise. Errors (5xx) still
# come through at their own level, so real problems aren't hidden.
logging.getLogger("werkzeug").setLevel(logging.WARNING)

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=COOKIE_SECURE,
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
)

job_queue = JobQueue()


@app.before_request
def require_login():
    """
    Gates everything - reports included, not just the queue API - behind
    the shared password whenever one is configured. With APP_PASSWORD
    unset this is a no-op, which keeps a local run exactly as frictionless
    as it was before hosting was a consideration.
    """
    if not APP_PASSWORD or session.get("authed"):
        return None
    if request.endpoint == "login":
        return None
    # The login page needs its own stylesheet to render as anything but
    # unstyled HTML. Only the stylesheet is exempt - it's the same shared
    # CSS every page uses and reveals nothing, whereas the scripts and the
    # reports themselves stay behind the password.
    if request.path == "/styles.css":
        return None
    # Answer the pollers with a status code their fetch() can react to,
    # rather than an HTML login page they'd try to parse as JSON.
    if request.path.startswith("/api/"):
        return jsonify({"error": "authentication required"}), 401
    return redirect(url_for("login", next=request.path))


@app.route("/login", methods=["GET", "POST"])
def login():
    if not APP_PASSWORD:
        return redirect("/")

    error = None
    if request.method == "POST":
        # compare_digest rather than == so a wrong guess takes the same
        # time to reject regardless of how much of the password it got
        # right.
        if secrets.compare_digest(request.form.get("password", ""), APP_PASSWORD):
            session["authed"] = True
            session.permanent = True
            # Only ever bounce back to a path on this site - taking the
            # raw ?next= would let a crafted link redirect someone
            # off-site straight after they log in.
            target = request.args.get("next", "/")
            if not target.startswith("/") or target.startswith("//"):
                target = "/"
            return redirect(target)
        error = "Incorrect password."

    return build_login_page(error), (401 if error else 200)


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


# Module level, not inside main(): under gunicorn nothing calls main(), so
# an app served that way would otherwise start with no stylesheet, no
# scripts, and an empty sidebar.
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
write_shared_assets(OUTPUT_FOLDER)
update_manifest(OUTPUT_FOLDER)

if not APP_PASSWORD and BIND_HOST not in ("127.0.0.1", "localhost"):
    log.warning(
        f"Serving on {BIND_HOST} with no APP_PASSWORD set - anyone who can reach this "
        "address can queue jobs against your OpenAI key. Set APP_PASSWORD."
    )


def main() -> None:
    url = f"http://127.0.0.1:{SERVE_PORT}/"
    log.info(f"Serving at {url} - press Ctrl+C to stop.")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    app.run(host=BIND_HOST, port=SERVE_PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
