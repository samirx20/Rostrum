"""Keys in a background window (app.background()): a window shown behind the person's work never becomes the active
window, and Qt fires a window shortcut (QML Shortcut, Qt.WindowShortcut) only in the active window, so a real key press
(QTest on the window) did nothing: every key check of Ctrl+K, Ctrl+R, Ctrl+Z ... silently could not test the keys.

Before Qt looks for the shortcut of a key (the ShortcutOverride event), every shortcut of the window is made an
application shortcut. One place covers every app (the kit's key map, AppShell, the app's own Shortcuts). The window is
never activated or raised; the person's own windows are never touched (only started when background() is true)."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt

_CONTEXT = Qt.ShortcutContext.ApplicationShortcut.value


class BackgroundKeys(QObject):
    def __init__(self, win):
        super().__init__(win)
        self._win = win

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.ShortcutOverride:
            for s in self._win.findChildren(QObject):
                if s.metaObject().className().startswith("QQuickShortcut") and s.property("context") != _CONTEXT:
                    s.setProperty("context", _CONTEXT)
        return False


def watch(app, win):
    """Make the window's shortcuts answer without it being the active window; the filter lives as long as the window."""
    keys = BackgroundKeys(win)
    app.installEventFilter(keys)
    return keys
