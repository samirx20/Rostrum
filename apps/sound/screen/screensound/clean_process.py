"""Runs the clean-up job (rostrum_sound.cleanup_job) in a process of its own and reads its lines, so the screen can end
it: `Cancel` kills the process, the cache keeps nothing that is not whole, and the half-made step folders are swept.

    job = CleanProcess(root, folder, clip_ids, on_progress)   # worker thread: job.run() -> "" or the error line
    job.kill()                                            # from the screen's thread
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

from rostrum_core.cache import Cache


class CleanProcess:
    def __init__(self, root: dict, folder, ids: list[str], on_progress: Callable[[str], None]):
        """`folder`: the song's project folder, which a take's relative `media` is read under (never the job's own)."""
        self.root, self.folder, self.ids, self.on_progress = root, folder, ids, on_progress
        self.proc: subprocess.Popen | None = None
        self.cancelled, self.started = False, time.time()

    def run(self) -> str:
        """The error line ("" = every take made, or the job was cancelled)."""
        folder = Path(tempfile.mkdtemp(prefix="clean-job-"))
        err, ok = "", False
        try:
            spec = folder / "spec.json"
            spec.write_text(json.dumps({"root": self.root, "folder": str(self.folder) if self.folder else None, "ids": self.ids}), encoding="utf-8")
            self.proc = subprocess.Popen(          # no -I: the job needs the same import paths as the screen
                [sys.executable, "-m", "rostrum_sound.cleanup_job", str(spec)], stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                env={**os.environ, "PYTHONPATH": os.pathsep.join(p for p in sys.path if p)})
            for line in self.proc.stdout:
                tag, _, text = line.rstrip("\n").partition(" ")
                if tag == "P":
                    self.on_progress(text)
                elif tag == "OK":
                    ok = True
                elif tag == "E":
                    err = f"Error: cleaned take: {text.removeprefix('Error: ')}"
            code = self.proc.wait()
            if not (ok or err or self.cancelled):
                err = f"Error: cleaned take: the clean-up process stopped (code {code}) without saying why."
        except Exception as e:  # noqa: BLE001  said on the screen, whatever it was
            err = f"Error: cleaned take: {e}"
        finally:
            shutil.rmtree(folder, ignore_errors=True)
        if self.cancelled:
            self._sweep()
            return ""
        return err

    def kill(self) -> None:
        """End the job now (OSError if it will not end: the caller says so)."""
        self.cancelled = True
        if self.proc is not None and self.proc.poll() is None:
            self.proc.kill()

    def _sweep(self):
        """The hidden `.tmp-…` step folders a stopped job left behind (the cache never reads them)."""
        for p in (Cache().root / "cleanup").glob(".tmp-*"):
            if p.stat().st_mtime >= self.started - 1:
                shutil.rmtree(p, ignore_errors=True)
