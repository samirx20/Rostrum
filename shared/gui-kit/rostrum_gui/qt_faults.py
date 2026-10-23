"""Qt's own warnings that mean the app is broken, made loud (kit `start` installs this, once per process).

Every Qt message still goes to stderr (the app's log). A few say the app did something Qt does not support and then
carried on, half working, e.g. a window deleted while one of its own click handlers was running (the start screen's
New, H43). Those are faults: in a scripted run (rostrum_core.userhome.scripted: a screenshot, a step run, the layout
check, a test) the first one ends the run with exit code 6, so a screen test can never pass over one. In a person's
run it goes to the log as "FAULT: …".

    watch()     install the handler (idempotent)
    found()     the faults seen so far, in order
    code(c)     the run's exit code: c, else EXIT when a scripted run saw a fault (the app's last line: sys.exit(code(c)))
"""
from __future__ import annotations

import sys

FAULTS = (
    "destroyed while one of its QML signal handlers is in progress",
    "must be called before loading QML",
    "This behavior is NOT supported",
)
EXIT = 6
_found: list[str] = []
_installed = False


def found() -> list[str]:
    return list(_found)


def code(c: int) -> int:
    from rostrum_core.userhome import scripted
    return c or (EXIT if _found and scripted() else 0)


def watch():
    global _installed
    if _installed:
        return
    from PySide6.QtCore import QCoreApplication, qInstallMessageHandler
    from rostrum_core.userhome import scripted

    def handler(_kind, context, message):
        if not any(f in message for f in FAULTS):
            print(message, file=sys.stderr, flush=True)
            return
        where = f" ({context.file}:{context.line})" if context.file else ""
        _found.append(message + where)
        if scripted():
            print(f"FAIL: Qt fault: {message}{where}", file=sys.stderr, flush=True)
            app = QCoreApplication.instance()
            if app is not None:
                app.exit(EXIT)
        else:
            print(f"FAULT: {message}{where}", file=sys.stderr, flush=True)

    qInstallMessageHandler(handler)
    _installed = True
