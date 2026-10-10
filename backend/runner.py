import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from graph.service import RunCancelled, execute_run

logger = logging.getLogger(__name__)


class RunManager:
    def __init__(self, store, executor=execute_run):
        self.store, self.execute = store, executor
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="research")

    def submit(self, run):
        self.pool.submit(self.work, run)

    def work(self, run):
        events, draft, sources = [], "", []
        flushed = 0

        def cancelled():
            return bool(self.store.run(run["user_id"], run["id"])["cancel_requested"])

        def progress(event):
            nonlocal draft, sources, flushed
            if event.get("type") == "delta":
                draft += event["text"]
            else:
                events.append({**event, "at": datetime.now(timezone.utc).isoformat()})
            if event.get("type") == "sources":
                sources = event["sources"]
            if event.get("type") != "delta" or time.monotonic() - flushed > 0.25:
                self.store.write_progress(run["user_id"], run["id"], events, draft, sources)
                flushed = time.monotonic()

        try:
            self.store.write_progress(run["user_id"], run["id"], events, draft, sources)
            result = self.execute(run, progress, cancelled)
            self.store.write_progress(run["user_id"], run["id"], events, draft, sources)
            self.store.finish(run["user_id"], run["id"], **result)
        except RunCancelled:
            self.store.finish(run["user_id"], run["id"], "cancelled", error="Research stopped. You can retry.", sources=sources)
        except Exception:
            logger.exception("Research run %s failed", run["id"])
            try:
                self.store.finish(run["user_id"], run["id"], "failed",
                    error="Research could not finish. Your question is saved; retry to continue.", sources=sources)
            except Exception:
                logger.exception("Could not persist failure for run %s", run["id"])

    def close(self):
        self.pool.shutdown(wait=True, cancel_futures=False)
