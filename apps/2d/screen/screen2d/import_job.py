"""One import's slow part running off the GUI thread (importer.py shows it): the worker thread and the cancel flag.
The worker only PLANS (importing.plan: read, download, parse, place); it never touches the document. `landed(plan, error
line, cancelled)` is called from the worker, and the GUI thread makes the one change (importing.apply)."""
from __future__ import annotations

import threading

from rostrum2d.io import importing


class Job:
    def __init__(self):
        self.cancelled, self._thread = False, None

    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, plan, landed, progress):
        """`plan(progress, cancelled)` runs importing.plan and returns its plan."""
        self.cancelled = False

        def work():
            try:
                p, line, stopped = plan(progress, lambda: self.cancelled), "", False
            except importing.Cancelled:
                p, line, stopped = None, "", True
            except Exception as e:  # noqa: BLE001  fail loudly, whatever it was
                p, line, stopped = None, e.line() if hasattr(e, "line") else f"Error: import: {e}", False
            landed(p, line, stopped)

        self._thread = threading.Thread(target=work, name="import", daemon=True)
        self._thread.start()

    def cancel(self) -> bool:
        """Ask the worker to stop at its next stage; False when nothing runs or it was already asked."""
        if not self.running() or self.cancelled:
            return False
        self.cancelled = True
        return True

    def wait(self, timeout_s: float):
        if self._thread is not None:
            self._thread.join(timeout_s)
