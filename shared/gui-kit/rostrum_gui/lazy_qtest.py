"""QTest, imported only when a step first uses it.

A step module (steps.py, stroke_steps.py ...) is imported by every launch, a person's too. Importing PySide6.QtTest at
its top made every launch count as scripted (rostrum_core.userhome.scripted: "a scripted hand (QtTest) drives this
run"): the person's window opened frameless and behind (app.show_behind) and their settings went to a temp folder
(Sam, 2026-10-27: no minimise / maximise / close, the window couldn't be dragged). Step modules take QTest from here."""
from __future__ import annotations


class _LazyQTest:
    def __getattr__(self, name):
        from PySide6.QtTest import QTest
        return getattr(QTest, name)


QTest = _LazyQTest()
