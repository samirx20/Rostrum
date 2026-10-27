"""`CanvasCursor` (import RostrumCursors 1.0): the canvas pointer as a QML item (CURSORS.md).

    CanvasCursor { kind: "rotate"; angle: layer.rotation + 45 }            // inside a handle's zone
    CanvasCursor { kind: "pick"; altBadge: "copy"; ctrlBadge: "deep" }     // over a layer
    CanvasCursor { kind: altHeld ? "dropper" : "none" }                    // Alt with a paint tool

It fills its parent and sets the pointer there; it never takes a press or a hover, so the zone under it works as
before. The topmost item with a pointer under the mouse wins (Qt Quick's rule): put one inside each zone.

    kind, angle, badge          the shape (cursors.KINDS), its turn (snaps to 5°) and its badge ("" = none)
    altBadge, ctrlBadge, shiftBadge   the badge while that key is held (first held of Alt, Ctrl, Shift wins)
    altHeld, ctrlHeld, shiftHeld      the keys held now, for bindings (`kind: altHeld ? … : …`)
    shown                       what it shows now ("pick+copy@0"), for checks

Held keys change the pointer the moment the key goes down or up, with the mouse still (CANVAS 1.1): one watcher per
window hears Alt / Ctrl / Shift and pokes every CanvasCursor; QQuickItem.setCursor applies a new pointer at once
when the mouse's last position is inside the item (Qt re-picks the window's pointer there), so no hover is needed.
The held state is read again from each mouse move and when the app comes back to the front (Alt+Tab never leaves
a stale copy badge). An unknown kind or badge raises (the scripted run fails) and the pointer shows `no` meanwhile.

It never calls its own `window()` or `parentItem()`: PySide makes what a getter like those returns a Python child of
the caller, so when the cursor went away (an automation lane closed, a song swapped in) the window's Python object went
with it, and the app's own handle on its window was dead ("Internal C++ object already deleted"; the window could no
longer close first at quit, and every binding then read the freed song). The window and parent come from their
change signals, or from lookups that tie nothing (`_window_now`, the `parent` property). It keeps no Python handle on
its parent either: a delegate whose Repeater's model shrinks is torn down parent first, and the parent's size links are
dropped by their own handles, never by calling into the half-destroyed parent.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QEvent, QObject, QPointF, Qt, Signal
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtQml import QmlElement
from PySide6.QtQuick import QQuickItem, QQuickWindow

from .cursors import check, cursor, scale_for, snap, STEP
from .gui_filter import GuiFilter

QML_IMPORT_NAME = "RostrumCursors"
QML_IMPORT_MAJOR_VERSION = 1
_KEYS = {Qt.Key.Key_Alt: 0, Qt.Key.Key_Control: 1, Qt.Key.Key_Shift: 2}
_MODS = (Qt.KeyboardModifier.AltModifier, Qt.KeyboardModifier.ControlModifier, Qt.KeyboardModifier.ShiftModifier)


class HeldKeys(GuiFilter):
    """Alt, Ctrl and Shift as held right now, heard on every window that shows a CanvasCursor."""
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.held = (False, False, False)
        self._windows: set[int] = set()

    def watch_window(self, win):
        if win is None or id(win) in self._windows:
            return
        self._windows.add(id(win))
        self.watch(win)
        win.destroyed.connect(lambda _=None, i=id(win): self._windows.discard(i))
        if len(self._windows) == 1:
            QGuiApplication.instance().applicationStateChanged.connect(self._again)

    def _again(self, *_):
        self._set(QGuiApplication.queryKeyboardModifiers())

    def _set(self, mods, key=None, down=False):
        held = [bool(mods & m) for m in _MODS]
        if key in _KEYS:                    # the key's own press / release: modifiers() lags it on some platforms
            held[_KEYS[key]] = down
        if tuple(held) != self.held:
            self.held = tuple(held)
            self.changed.emit()

    def on_event(self, obj, event):
        t = event.type()
        if t in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            self._set(event.modifiers(), event.key(), t == QEvent.Type.KeyPress)
        elif t == QEvent.Type.MouseMove:
            self._set(event.modifiers())
        return False


HELD = HeldKeys()


def _str_prop(name):
    attr, sig = f"_{name}", f"{name}Changed"

    def get(self):
        return getattr(self, attr)

    def put(self, value):
        value = value or ""
        if value != getattr(self, attr):
            old = getattr(self, attr)
            setattr(self, attr, value)
            try:
                self._apply()
            except ValueError:
                setattr(self, attr, old)
                self.setCursor(QCursor(Qt.CursorShape.ForbiddenCursor))
                raise
            getattr(self, sig).emit()
    return get, put


@QmlElement
class CanvasCursor(QQuickItem):
    kindChanged, angleChanged, badgeChanged = Signal(), Signal(), Signal()
    altBadgeChanged, ctrlBadgeChanged, shiftBadgeChanged = Signal(), Signal(), Signal()
    heldChanged, shownChanged = Signal(), Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._kind, self._angle, self._badge = "pick", 0.0, ""
        self._altBadge = self._ctrlBadge = self._shiftBadge = ""
        self._shown, self._links, self._win = "", (), None
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setAcceptHoverEvents(False)
        self.parentChanged.connect(self._follow)
        self.windowChanged.connect(self._window)
        HELD.changed.connect(self._held)

    kind = Property(str, *_str_prop("kind"), notify=kindChanged)
    badge = Property(str, *_str_prop("badge"), notify=badgeChanged)
    altBadge = Property(str, *_str_prop("altBadge"), notify=altBadgeChanged)
    ctrlBadge = Property(str, *_str_prop("ctrlBadge"), notify=ctrlBadgeChanged)
    shiftBadge = Property(str, *_str_prop("shiftBadge"), notify=shiftBadgeChanged)

    def _get_angle(self):
        return self._angle

    def _set_angle(self, a):
        turned, self._angle = snap(a) != snap(self._angle), float(a)
        if turned:
            self._apply()
            self.angleChanged.emit()
    angle = Property(float, _get_angle, _set_angle, notify=angleChanged)

    altHeld = Property(bool, lambda self: HELD.held[0], notify=heldChanged)
    ctrlHeld = Property(bool, lambda self: HELD.held[1], notify=heldChanged)
    shiftHeld = Property(bool, lambda self: HELD.held[2], notify=heldChanged)
    shown = Property(str, lambda self: self._shown, notify=shownChanged)

    def showing(self) -> tuple[str, str]:
        """(kind, badge) shown now: the first held key with a badge of its own, else `badge`."""
        for on, b in zip(HELD.held, (self._altBadge, self._ctrlBadge, self._shiftBadge)):
            if on and b:
                return self._kind, b
        return self._kind, self._badge

    def _apply(self):
        kind, badge = self.showing()
        check(kind, badge)
        win = self._win
        scale = scale_for(win)
        self.setCursor(cursor(kind, self._angle, badge, scale, win.devicePixelRatio() if win else 1.0))
        shown = f"{kind}{'+' + badge if badge else ''}@{snap(self._angle) * STEP}"
        if shown != self._shown:
            self._shown = shown
            self.shownChanged.emit()

    def componentComplete(self):            # noqa: N802 (Qt's name)
        """Made: fill the parent and show the pointer now. In some places (a Loader's or a delegate's item, Sound's
        roll) the parent was set before the parentChanged link or the window came first, which left the item 0×0
        and `shown` empty until some value changed."""
        super().componentComplete()
        self._follow(self.property("parent"))
        if self._win is None and (win := self._window_now()) is not None:
            self._window(win)

    def _window_now(self):
        """The window showing this item, found without `self.window()` (see the module's note)."""
        for w in QGuiApplication.topLevelWindows():
            if isinstance(w, QQuickWindow) and w.contentItem().isAncestorOf(self):
                return w
        return None

    def _held(self):
        self.heldChanged.emit()             # bindings on altHeld … may change kind first
        self._apply()

    def _window(self, win):
        self._win = win
        HELD.watch_window(win)
        if win is not None:
            self._apply()

    def _follow(self, parent):
        for link in self._links:
            QObject.disconnect(link)
        self._links = ()
        if parent is not None:
            self._links = (parent.widthChanged.connect(self._fit), parent.heightChanged.connect(self._fit))
            self._fit()

    def _fit(self):
        parent = self.property("parent")
        if parent is not None:
            self.setPosition(QPointF(0, 0))
            self.setSize(parent.size())
