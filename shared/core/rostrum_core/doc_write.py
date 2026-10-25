"""A window's document file, written without the person waiting (live.Live.fold_if_quiet).

Python runs one thread's Python at a time, so making the text on another thread still delays the screen's thread
(it waits for its turn, up to 5 ms each time it asks). So the text is made on the screen's thread, a slice of a few
milliseconds at a time between the person's events (`step`, which the window's link calls from a zero timer), and
only hashing it and writing the file, which let other threads run, go to a thread of their own. The tree is the
document as it stood (never changed in place: edits.fork), so nothing is copied. A failed write is kept for the
caller to say loudly (`error`); `finish` makes the rest at once and waits (Save, close, a script reading the file).
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from .storage import canonical_pieces, write_document

_POOL = ThreadPoolExecutor(1, thread_name_prefix="document-file")   # (its thread is waited for at exit: a write ends)


class DocWrite:
    def __init__(self, path, kind, data, seq, last):
        self.path, self.format, self.version = path, kind.format, kind.version
        self.data, self.seq, self.last = data, seq, last
        self._pieces, self._made, self._job = canonical_pieces(data), [], None

    def step(self, budget=0.003) -> bool:
        """Make about `budget` seconds more of the text; once it is whole, hand it to the writing thread. True while
        there is text still to make."""
        if self._job is not None:
            return False
        end, made = time.perf_counter() + budget, self._made
        for piece in self._pieces:
            made.append(piece)
            if time.perf_counter() > end:
                return True
        t = self.last.t if self.last is not None else 0.0
        self._job = _POOL.submit(write_document, self.path, self.format, self.version, self.seq, t, "".join(made))
        self._made = None
        return False

    def done(self) -> bool:
        return self._job is not None and self._job.done()

    def finish(self):
        """Make the rest now and wait for the file (Save, close, a script)."""
        while self.step(1.0):
            pass
        self._job.exception()

    def error(self):
        return self._job.exception()

    def result(self):
        return self._job.result()
