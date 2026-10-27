"""Which part of the work the person last pressed in: the arrangement, or the Editor (bottom dock, Editor tab). Ctrl+A
takes everything of its kind there (select_slots.selectAll): the Editor's track's notes, or the arrangement's.

It was set only by the presses some items handled themselves (a lane, the roll's canvas, a track's name), so a press on
the Editor's own buttons (Select, Draw, Note ▾) left it on "arrange" from the track-name click that opened the Editor;
Ctrl+A there selected that track (it was the selection), and after a panel edit (the notes now the selection) every
note of the song, and the Editor followed to the first track (critic r10 must-fix 1). Watched on the window, before
any item takes the press, so every press counts. A press elsewhere (the settings panel, the top bar) keeps the area.

A press inside an open popup (a popover, a menu, a choice's list: the window's overlay) belongs to the area that
opened it, so it keeps the area too. Repeat's Until list opens over the arrangement, so picking "Next marker" with
the mouse counted as a press in the arrangement and the next Ctrl+A took every track (critic r11 must-fix 1).
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, QRectF
from PySide6.QtQuick import QQuickItem
from rostrum_gui.gui_filter import GuiFilter
from rostrum_gui.meta import class_name

AREAS = (("soundDock", "roll"), ("soundArrangement", "arrange"))


class PressArea(GuiFilter):
    def __init__(self, win, bridge_of):
        super().__init__(win)
        self.win, self.bridge_of, self.items = win, bridge_of, {}
        self.watch(win)

    def _item(self, name):
        it = self.items.get(name)
        if it is None:
            it = self.items[name] = self.win.findChild(QQuickItem, name)
        return it

    def _overlay(self):
        """The window's popup layer (made by Qt the first time a popup opens)."""
        ov = self.items.get("overlay")
        if ov is None:
            ov = next((c for c in self.win.contentItem().childItems()
                       if class_name(c) == "QQuickOverlay"), None)
            if ov is not None:
                self.items["overlay"] = ov
        return ov

    def _in_popup(self, at: QPointF) -> bool:
        ov = self._overlay()
        return ov is not None and any(
            c.isVisible() and c.mapRectToScene(QRectF(0, 0, c.width(), c.height())).contains(at)
            for c in ov.childItems())

    def on_event(self, obj, event):
        if obj is not self.win or event.type() != QEvent.Type.MouseButtonPress:
            return False
        p = event.position()
        if self._in_popup(QPointF(p.x(), p.y())):
            return False
        for name, area in AREAS:
            it = self._item(name)
            if it is None or not it.isVisible() or (name == "soundDock" and it.property("tool") != "editor"):
                continue
            if it.mapRectToScene(QRectF(0, 0, it.width(), it.height())).contains(QPointF(p.x(), p.y())):
                bridge = self.bridge_of()
                if bridge is not None:
                    bridge.focusArea(area)
                break
        return False
