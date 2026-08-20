"""
Background job queue for the web app (app.py): submitted URLs are processed
one at a time by a single worker thread, so a second submission while one
video is still transcribing/translating waits its turn rather than running
concurrently and competing for the same OpenAI rate limits / ffmpeg CPU.
"""
import logging
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from main import process_video

log = logging.getLogger("youtube-transcriber")


@dataclass
class Job:
    id: str
    url: str
    status: str = "queued"  # queued -> processing -> done | error
    log_lines: list = field(default_factory=list)
    error: Optional[str] = None
    result_files: list = field(default_factory=list)
    submitted_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "status": self.status,
            "log_lines": list(self.log_lines),
            "error": self.error,
            "result_files": list(self.result_files),
        }


class _JobLogHandler(logging.Handler):
    """Mirrors this job's slice of the shared logger into job.log_lines, so
    the web UI can show live progress without the browser needing direct
    access to the server's stdout."""

    def __init__(self, job: Job):
        super().__init__()
        self.job = job
        self.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        self.job.log_lines.append(self.format(record))


class JobQueue:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()
        self._pending: queue.Queue = queue.Queue()
        threading.Thread(target=self._worker, daemon=True).start()

    def submit(self, url: str) -> Job:
        job = Job(id=uuid.uuid4().hex, url=url)
        with self._lock:
            self._jobs[job.id] = job
            self._order.append(job.id)
        self._pending.put(job.id)
        return job

    def list_jobs(self) -> list:
        with self._lock:
            return [self._jobs[job_id] for job_id in reversed(self._order)]

    def _worker(self) -> None:
        while True:
            job_id = self._pending.get()
            job = self._jobs[job_id]
            job.status = "processing"

            handler = _JobLogHandler(job)
            log.addHandler(handler)
            try:
                out_paths = process_video(job.url)
                job.result_files = [p.name for p in out_paths]
                job.status = "done"
            except Exception as exc:
                log.exception(f"Failed to process {job.url}")
                job.error = str(exc)
                job.status = "error"
            finally:
                log.removeHandler(handler)
