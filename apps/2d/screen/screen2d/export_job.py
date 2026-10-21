"""One export running off the GUI thread (exporter.py shows it): the worker thread, the engine it started (kept, so
Cancel can stop it by its own handle) and the cancel flag. `landed(facts, error line)` is called from the worker;
a cancelled run lands with no error, and exporting.run has already removed its unfinished files."""
from __future__ import annotations

import threading

from rostrum2d.mcp import exporting


class Job:
    def __init__(self, engine_factory=None):
        self.engine_factory, self.engine, self.cancelled, self._thread = engine_factory, None, False, None

    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, export, landed):
        """`export(make_engine)` runs exporting.run and returns its facts."""
        self.engine, self.cancelled = None, False

        def make_engine():
            self.engine = (self.engine_factory or exporting._engine)()
            return self.engine

        def work():
            try:
                landed(export(make_engine), "")
            except Exception as e:  # noqa: BLE001  fail loudly, whatever it was (a cancel is the one expected stop)
                landed({}, "" if self.cancelled else e.line() if hasattr(e, "line")
                       else f"Error: export: {type(e).__name__}: {e}")

        self._thread = threading.Thread(target=work, name="export", daemon=True)
        self._thread.start()

    def cancel(self) -> bool:
        """Stop the engine; False when there is nothing to stop (not running, not started yet, already cancelled)."""
        if not self.running() or self.engine is None or self.cancelled:
            return False
        self.cancelled = True
        if self.engine.proc.poll() is None:
            self.engine.proc.kill()
        return True

    def wait(self, timeout_s: float):
        if self._thread is not None:
            self._thread.join(timeout_s)
