"""Qt's own warnings that mean the app is broken, made loud (kit `start` installs this, once per process).

Every Qt message still goes to stderr (the app's log). A few say the app did something Qt does not support and then
carried on, half working, e.g. a window deleted while one of its own click handlers was running (the start screen's
New, H43). Those are faults: in a scripted run (rostrum_core.userhome.scripted: a screenshot, a step run, the layout
check, a test) the first one ends the run with exit code 6, so a screen test can never pass over one. In a person's
run it goes to the log as "FAULT: …".

A QML `TypeError` / `ReferenceError` (Qt prints "file.qml:24: TypeError: …" and the handler does nothing) is a fault
too: that is how the empty-state button was dead in every app for a long time without a test failing.

A Python error that escapes into Qt (a slot, a QML call into Python, an event filter, a worker thread) is a fault the
same way: PySide would only print it and carry on, so `watch` routes it here (sys.excepthook, threading.excepthook)
with its traceback. The app survives it; a scripted run fails on it.

In a person's run a fault is also told to the person, never only to the log: every window's bridge listens (`tell`)
and shows one plain line in red ("Select inside didn't work: …"), so a button that fails is never silent (critic r4, M2).

    watch()     install the handlers (idempotent)
    tell(fn)    fn(line) hears each fault in plain words (kept weakly: a closed window's bridge drops out)
    python_error(where, what="")  report the Python error being handled now (gui_filter.py's guard calls it); `what`
                names what the person did ("Select inside") for the line they see
    found()     the faults seen so far, in order
    code(c)     the run's exit code: c, else EXIT when a scripted run saw a fault (the app's last line: sys.exit(code(c)))
"""
from __future__ import annotations

import sys
import traceback
import weakref

FAULTS = (
    "destroyed while one of its QML signal handlers is in progress",
    "must be called before loading QML",
    "This behavior is NOT supported",
    "TypeError:",                       # QML ran code that cannot work: a dead button, a missing value (H61: EmptyHint)
    "ReferenceError:",
)
EXIT = 6
_found: list[str] = []
_installed = False
_told: list = []            # weak references to the listeners (`tell`)


def found() -> list[str]:
    return list(_found)


def code(c: int) -> int:
    from rostrum_core.userhome import scripted
    return c or (EXIT if _found and scripted() else 0)


def tell(fn):
    """`fn(line)` hears every fault from now on, in the person's words (a bound method is kept weakly)."""
    _told.append(weakref.WeakMethod(fn) if hasattr(fn, "__self__") else (lambda f=fn: f))


def _say(line: str):
    for ref in list(_told):
        fn = ref()
        if fn is None:
            _told.remove(ref)
        else:
            try:
                fn(line)
            except RuntimeError:            # its window's object is already gone
                _told.remove(ref)


def _fault(message: str, where: str = "", said: str = ""):
    _found.append(message + where)
    _say(said or "Something on the screen didn't work. The details are in the log.")
    from rostrum_core.userhome import scripted
    if scripted():
        print(f"FAIL: {message}{where}", file=sys.stderr, flush=True)
        from PySide6.QtCore import QCoreApplication
        app = QCoreApplication.instance()
        if app is not None:
            app.exit(EXIT)
    else:
        print(f"FAULT: {message}{where}", file=sys.stderr, flush=True)


def _python(kind, value, tb, where="", what=""):
    text = "".join(traceback.format_exception(kind, value, tb)).rstrip()
    print(text, file=sys.stderr, flush=True)
    _fault(f"Python error{where}: {kind.__name__}: {value}", "",
           f"{what or 'That'} didn't work: an error in the app ({kind.__name__}: {value}). The details are in the log.")


def python_error(where: str, what: str = ""):
    """Report the exception being handled now (call inside `except`), raised in `where`; `what` is what the person
    did, in their words."""
    _python(*sys.exc_info(), where=f" in {where}", what=what)


def watch():
    global _installed
    if _installed:
        return
    import threading
    from PySide6.QtCore import qInstallMessageHandler

    def handler(_kind, context, message):
        if not any(f in message for f in FAULTS):
            print(message, file=sys.stderr, flush=True)
            return
        _fault(f"Qt fault: {message}", f" ({context.file}:{context.line})" if context.file else "")

    qInstallMessageHandler(handler)
    sys.excepthook = _python                                    # a slot's or a QML call's error (PySide reports here)
    threading.excepthook = lambda a: _python(a.exc_type, a.exc_value, a.exc_traceback,
                                             f" in thread {a.thread.name if a.thread else '?'}")
    _installed = True
