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
press that follows is dropped too. A press sent straight to the window (a script's) has no such question first and
is judged on the press itself, which the window sees before its shortcut runs.
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


def typing_in_field(win=None) -> bool:
    """A text field has the keyboard (the same test as the kit's OpenPopups.typing). The window's own focus item counts:
    the app's `focusObject` is empty while the window is not the active one (a check window kept behind the person's
    work), and every digit after the first typed into a field there was dropped as part of a word (2D r11b)."""
    f = QGuiApplication.focusObject() or (win.activeFocusItem() if hasattr(win, "activeFocusItem") else None)
    mo = f.metaObject() if f is not None else None
    return mo is not None and mo.indexOfProperty("cursorPosition") >= 0 and mo.indexOfProperty("selectByMouse") >= 0


class TypedWord(GuiFilter):
    def __init__(self, win, clock=time.monotonic):
        super().__init__(win)
        self.clock, self.last, self.dropping, self.judged = clock, -1.0, None, None
        self.watch(win)

    def _word(self, event, win=None) -> bool:
        """Is this plain key part of a word (and so to be dropped)? Each press is judged once."""
        if event.isAutoRepeat() or not plain(event) or typing_in_field(win):
            return False
        now, before = self.clock(), self.last
        self.last = now
        # a Shift key is a command chosen on purpose (Shift+C twice), never dropped; it still starts a word ("Drums")
        return now - before < WORD_S and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier

    def on_event(self, obj, event):
        t = event.type()
        if t == QEvent.Type.ShortcutOverride:               # the usual way: asked before any shortcut is tried
            self.judged = (event.key(), event.timestamp())     # the press that follows has the same stamp
            if self._word(event, obj):
                self.dropping = event.key()
                event.accept()                              # "the focus wants it": Qt runs no shortcut for it
                return True
            return False
        if t != QEvent.Type.KeyPress:
            return False
        if self.dropping is not None and event.key() == self.dropping:
            self.dropping = self.judged = None
            return True                                     # the press of a key that was part of a word
        if self.judged == (event.key(), event.timestamp()):   # judged on its override: let it be
            self.judged = None
            return False
        return self._word(event, obj)                       # a press sent straight to the window (no override first):
                                                            # the shortcut runs from it, so it is judged here


def watch(win):
    """Install on a window (app.start does, for every app window)."""
    return TypedWord(win)
