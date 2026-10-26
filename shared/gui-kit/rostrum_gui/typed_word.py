"""Typing with no box focused is not a run of commands. Single keys are commands when nothing types (M adds a marker,
R records, Space plays), so a word typed with nothing focused ("drums") ran R and M: a marker appeared and the next
letter went into its name (Sound critic r9 and r10). Every earlier fix gave the keys to a field that *has* the
keyboard; with none focused there was nothing to give them to, so the shortcuts still ran.

The rule, one place for every app: a plain key (a letter, a digit or Space, no Ctrl / Alt / Meta) that comes within
WORD_S of the plain key before it is part of a word, and does nothing: its shortcut is never tried and no item gets
it. A person pressing one command key waits longer than that between keys; a word comes faster. The first key of the
word still runs (it can't be told from a lone command key yet). A text field with the keyboard is never touched (its
letters are its own), and a held key's auto-repeats are left alone.

Watched on the window before Qt tries its shortcuts: Qt asks the window's focus object whether it wants a key
(ShortcutOverride) before any shortcut runs; taking that event here keeps the shortcut from running, and the key's
press that follows is dropped too.
"""
from __future__ import annotations

import time

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QGuiApplication

from .gui_filter import GuiFilter

WORD_S = 0.3
COMMAND_MODS = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier


def plain(event) -> bool:
    k = event.key()
    return not (event.modifiers() & COMMAND_MODS) and (
        Qt.Key.Key_A <= k <= Qt.Key.Key_Z or Qt.Key.Key_0 <= k <= Qt.Key.Key_9 or k == Qt.Key.Key_Space)


def typing_in_field() -> bool:
    """A text field has the keyboard (the same test as the kit's OpenPopups.typing)."""
    f = QGuiApplication.focusObject()
    mo = f.metaObject() if f is not None else None
    return mo is not None and mo.indexOfProperty("cursorPosition") >= 0 and mo.indexOfProperty("selectByMouse") >= 0


class TypedWord(GuiFilter):
    def __init__(self, win, clock=time.monotonic):
        super().__init__(win)
        self.clock, self.last, self.dropping = clock, -1.0, None
        self.watch(win)

    def on_event(self, obj, event):
        t = event.type()
        if t == QEvent.Type.KeyPress and self.dropping is not None and event.key() == self.dropping:
            self.dropping = None
            return True                                 # the press of a key that was part of a word
        if t != QEvent.Type.ShortcutOverride or event.isAutoRepeat() or not plain(event) or typing_in_field():
            return False
        now, before = self.clock(), self.last
        self.last = now
        if now - before < WORD_S:
            self.dropping = event.key()
            event.accept()                              # "the focus wants it": Qt runs no shortcut for it
            return True
        return False


def watch(win):
    """Install on a window (app.start does, for every app window)."""
    return TypedWord(win)
