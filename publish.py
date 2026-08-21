"""
Copies finished reports into docs/ so GitHub Pages can serve them.

Processing stays on your machine - YouTube blocks the datacenter IPs that
hosting providers run on, so a server can neither download audio nor even
read a video's metadata (verified against a live deployment). This just
publishes the finished HTML, which is all a reader actually needs.

Run with:  python3 publish.py          (prepare docs/, then commit yourself)
           python3 publish.py --push   (prepare, commit, and push in one go)
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from assets import CSS, REPORT_JS, SIDEBAR_JS
from config import OUTPUT_FOLDER
from report_builder import build_index_page, manifest_entries, update_manifest

REPO_ROOT = Path(__file__).parent
DOCS = REPO_ROOT / "docs"


def _clean_docs() -> None:
    """
    Removes only the file types this script generates, rather than wiping
    the directory - so a stray note or CNAME file someone put here on
    purpose survives, while a report deleted from transcripts/ doesn't
    linger on the published site.
    """
    if not DOCS.exists():
        return
    for pattern in ("*.html", "*.js", "*.css"):
        for path in DOCS.glob(pattern):
            path.unlink()


def publish() -> int:
    entries = manifest_entries(OUTPUT_FOLDER)
    if not entries:
        print(f"No reports found in {OUTPUT_FOLDER} - nothing to publish.")
        return 0

    DOCS.mkdir(parents=True, exist_ok=True)
    _clean_docs()

    for entry in entries:
        shutil.copy2(OUTPUT_FOLDER / entry["file"], DOCS / entry["file"])

    # Written from the same constants app.py serves, so the published site
    # can't drift from the local one. home.js is deliberately excluded:
    # it drives the submission queue, which has no worker behind it here.
    (DOCS / "styles.css").write_text(CSS, encoding="utf-8")
    (DOCS / "sidebar.js").write_text(SIDEBAR_JS, encoding="utf-8")
    (DOCS / "report.js").write_text(REPORT_JS, encoding="utf-8")

    # Recomputed from docs/ itself rather than copied, so it always
    # matches what actually got published.
    update_manifest(DOCS)
    (DOCS / "index.html").write_text(build_index_page(manifest_entries(DOCS)), encoding="utf-8")

    # Without this, GitHub runs the published files through Jekyll, which
    # silently skips anything whose name starts with an underscore.
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")

    print(f"Published {len(entries)} transcript{'s' if len(entries) != 1 else ''} to {DOCS}")
    return len(entries)


def git_push(count: int) -> None:
    subprocess.run(["git", "add", "docs"], cwd=REPO_ROOT, check=True)

    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=REPO_ROOT
    ).returncode
    if staged == 0:
        print("No changes to publish - docs/ already matches transcripts/.")
        return

    subprocess.run(
        ["git", "commit", "-m", f"Publish {count} transcript{'s' if count != 1 else ''}"],
        cwd=REPO_ROOT, check=True,
    )
    subprocess.run(["git", "push"], cwd=REPO_ROOT, check=True)
    print("Pushed. GitHub Pages usually redeploys within a minute.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy finished transcripts into docs/ for GitHub Pages."
    )
    parser.add_argument(
        "--push", action="store_true",
        help="Also commit docs/ and push. Omitted, this only stages the files locally - "
             "publishing is public, so it's an explicit step rather than a side effect.",
    )
    args = parser.parse_args()

    count = publish()
    if not count:
        return

    if args.push:
        git_push(count)
    else:
        print("\nNot pushed. To publish these publicly:")
        print("  git add docs && git commit -m 'Publish transcripts' && git push")


if __name__ == "__main__":
    main()
