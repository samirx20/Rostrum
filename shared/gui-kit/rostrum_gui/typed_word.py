"""Typing with no box focused is not a run of commands. Single keys are commands when nothing types (M adds a marker,
R records, Space plays), so a word typed with nothing focused ("drums") ran R and M: a marker appeared and the next
letter went into its name (Sound critic r9 and r10).

The rule, one place for every app: a plain key (a letter or a digit, no Ctrl / Alt / Meta / Shift) is dropped only
when the key before it, less than WORD_S earlier, was a letter that ran no shortcut of its own: that letter started a
word ("drums": D is no command, so R, U, M and S are the rest of the word and run nothing). A dropped key keeps the
word going. Never dropped (Sound critic r11, a speed-only rule lost real shortcuts):
- a key right after a shortcut that ran (B then V, Q then Space: two commands, however quick);
- Space (Space-Space starts and stops);
- a Shift key (a command chosen on purpose, Shift+C twice);
- a key going into a text field (its letters are its own), and a held key's auto-repeats.

"A shortcut ran" is told by the kit's KeyShortcut itself: each one calls `ran()` (the `typedWord` context object) when
it fires, so a letter whose shortcut is switched off counts as a word's start. The keys are watched on the window
before Qt tries its shortcuts: Qt asks whether the focus wants a key (ShortcutOverride) before any shortcut runs;
taking that event here keeps the shortcut from running, and the key's press that follows is dropped too. A press sent
straight to the window (a script's) has no such question first and is judged on the press itself.

Whether a text field has the keys is asked of the window (`activeFocusItem`), not the application: a window kept
behind the person's work has no application focus object, and fast typing into its fields lost every key after the
first (critic r11: "29.1" -> "2.").
"""
from __future__ import annotations

import time

from PySide6.QtCore import Q_ARG, QEvent, QMetaObject, Qt, QTimer, Slot

from .ack import ACK
from .gui_filter import GuiFilter
from .meta import has_method, has_property

WORD_S = 0.3
COMMAND_MODS = (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.MetaModifier | Qt.KeyboardModifier.ShiftModifier)


def letter(k) -> bool:
    return Qt.Key.Key_A <= k <= Qt.Key.Key_Z


def droppable(event) -> bool:
    """A key that may be the rest of a word: a plain letter or digit (never Space, never with a modifier)."""
    k = event.key()
    return not (event.modifiers() & COMMAND_MODS) and (letter(k) or Qt.Key.Key_0 <= k <= Qt.Key.Key_9)


def is_field(item) -> bool:
    """`item` is a text field (the same test as the kit's OpenPopups.typing)."""
    return item is not None and has_property(item, "cursorPosition") and has_property(item, "selectByMouse")


def typing_in_field(win) -> bool:
    """A text field of `win` has the keys. Asked of the window: the app's focus object is empty while the window is
    not the active one (a check window kept behind the person's work), and every key after the first typed into a
    field there was dropped (2D r11b, Sound critic r11)."""
    return is_field(win.activeFocusItem() if hasattr(win, "activeFocusItem") else None)


def pass_unusable_key(win, event) -> None:
    """A number box with the caret in it (FieldFrame.numeric) cannot use Delete with nothing after the caret, or a letter: it
    claims every key before shortcuts are tried and QML cannot undo that, so it is asked here, first (FieldFrame.passKey)."""
    item = win.activeFocusItem() if hasattr(win, "activeFocusItem") else None
    if item is None or not has_method(item, "passKey(QVariant)") or event.isAutoRepeat():
        return
    if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier):
        return
    name = "Delete" if event.key() == Qt.Key.Key_Delete else event.text()
    if name and (name == "Delete" or name.isprintable()):       # (Enter's text is "\r": no letter, so never "type a number" after a typed 90 + Enter)
        QMetaObject.invokeMethod(item, "passKey", Qt.ConnectionType.DirectConnection, Q_ARG("QVariant", name))
        if name != "Delete" and item.property("passing"):     # a letter the box can't hold, on its way to a shortcut:
            return item, name                                 # if none runs, the box says so (TypedWord.unheard)
    return None


def say_unheard(item, name) -> None:
    """No shortcut took the letter a number box passed on: the box says it wants a number (NumberField.saysLetter), so
    the key never vanishes (INTERACTION.md principle 8)."""
    try:
        while item is not None and not has_method(item, "saysLetter(QVariant)"):
            item = item.parentItem()            # (the caret is in the box's own text input)
        if item is not None:
            QMetaObject.invokeMethod(item, "saysLetter", Qt.ConnectionType.DirectConnection, Q_ARG("QVariant", name))
    except RuntimeError:        # the box went away meanwhile
        pass


class TypedWord(GuiFilter):
    def __init__(self, clock=time.monotonic):
        super().__init__()
        self.clock = clock
        self.last, self.in_word = -1.0, False       # the previous plain key's time; it was a word's letter (no shortcut ran)
        self.dropping = self.judged = None
        self.shortcuts = 0                          # shortcuts fired so far (a passed letter's turn checks it moved)

    @Slot()
    def ran(self):
        """A shortcut just fired (KeyShortcut calls this): the key that fired it started no word. What it runs is a
        person's press: drawn first, then run (ack.py)."""
        self.in_word = False
        self.shortcuts += 1
        ACK.key()

    def _heard(self, passed, count):
        """The key's turn is over: a letter a number box passed on that no shortcut took is said, not lost."""
        if self.shortcuts == count:
            say_unheard(*passed)

    def _drop(self, win, event) -> bool:
        """Is this key the rest of a word (and so to be dropped)? Each press is judged once."""
        if event.isAutoRepeat() or typing_in_field(win):
            return False
        now, before, in_word = self.clock(), self.last, self.in_word
        drop = droppable(event) and in_word and now - before < WORD_S
        self.last = now
        # a letter starts (or goes on with) a word until its shortcut, if it has one, says it ran ("Drums" too)
        self.in_word = drop or (letter(event.key()) and not event.modifiers() & (COMMAND_MODS & ~Qt.KeyboardModifier.ShiftModifier))
        return drop

    def on_event(self, obj, event):
        t = event.type()
        if t == QEvent.Type.ShortcutOverride:               # the usual way: asked before any shortcut is tried
            passed = pass_unusable_key(obj, event)
            if passed:
                QTimer.singleShot(0, lambda c=self.shortcuts: self._heard(passed, c))
            self.judged = (event.key(), event.timestamp())     # the press that follows has the same stamp
            if self._drop(obj, event):
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
        return self._drop(obj, event)                       # a press sent straight to the window (no override first)


def make(clock=time.monotonic) -> TypedWord:
    """One per window's engine: set as the `typedWord` context object before the window loads (KeyShortcut reports to
    it), then `watch(win)`."""
    return TypedWord(clock)
