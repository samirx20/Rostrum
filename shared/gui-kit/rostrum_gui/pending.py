"""Typing not yet entered, finished before the selection moves (as Figma does).

A field (FieldFrame) commits on Enter, Tab or leaving it. When the selection changes while a field has the keys,
`finish_typing()` makes it let go first: its commit lands while the old selection still stands, so typed text goes to
the item it was typed for, never to the newly selected one, and the field then shows the new item's value. A kit
field's text box has a `pending` property (FieldFrame); other text boxes (a search box) keep their focus.
"""
from __future__ import annotations

from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickWindow


def finish_typing() -> None:
    """Every window's focused kit field lets go of the keys, which commits what is typed in it (FieldFrame)."""
    app = QGuiApplication.instance()
    if not isinstance(app, QGuiApplication):        # no screen (a script, a test without one): nothing is typed
        return
    for window in app.topLevelWindows():
        item = window.activeFocusItem() if isinstance(window, QQuickWindow) else None
        if item is not None and item.property("pending") is not None:
            item.setFocus(False)
