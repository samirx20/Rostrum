"""The start-up watchdog: if the window hasn't shown SECONDS after start, every thread's stack goes to the log (stderr:
the installed app's log, rostrum.pyw), again every SECONDS until it shows, so a start that sits without a window says
where it is waiting. faulthandler's own timer thread writes it, so it works even while Python is stuck in native code.
"""
from __future__ import annotations

import faulthandler
import sys
import time

SECONDS = 20


def arm():
    if sys.stderr is None or not hasattr(sys.stderr, "fileno"):     # nowhere to write it (pythonw without a log)
        return
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} start: a stack dump follows every {SECONDS} s until the window shows",
          file=sys.stderr, flush=True)
    faulthandler.dump_traceback_later(SECONDS, repeat=True, file=sys.stderr)


def shown_on(win):
    """Disarm when `win` first draws a frame (the person can see it)."""
    def done():
        faulthandler.cancel_dump_traceback_later()
        win.frameSwapped.disconnect(done)
    win.frameSwapped.connect(done)
