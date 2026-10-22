"""CanvasView's place: where the person left the view, for "reopen at the same place" (rostrum_core.places; the app's
`place` hook puts `view.place()` in its place dict, `restore_place` hands it back to `view.restore_place(p)`).
A fitted view is remembered as "fitted" and fits again once the view has its size and content (the window may be a
different size now); any other view returns to the same zoom and pan.
"""
from __future__ import annotations

from PySide6.QtCore import Slot

from .view_menu import entries


class ViewPlace:
    def place(self) -> dict:
        return {"zoom": self._z, "panX": self._px, "panY": self._py, "fitted": self._fitted}

    def restore_place(self, p: dict) -> None:
        """A saved place back on; a bad one (wrong types) fails loudly."""
        self._z = max(0.01, min(64.0, float(p["zoom"])))
        self._want_fit = bool(p.get("fitted"))
        self._set(float(p["panX"]), float(p["panY"]), fitted=False)
        self._refit()

    def _refit(self) -> None:
        if self._want_fit and self._content is not None and self._w and self._h:
            self._want_fit = False
            self.fit_box(self._content)

    @Slot(result="QVariantList")
    def menu(self):
        return entries(self._z, self._fitted)

    @Slot(float)
    def zoomTo(self, percent):
        self.zoomAt(percent / 100.0, self._w / 2, self._h / 2)

    @Slot(str)
    def pick(self, value):
        """A row of menu() chosen: "job:<view job>" or "zoom:<percent>"."""
        kind, _, arg = value.partition(":")
        if kind == "job":
            self.job(arg)
        elif kind == "zoom":
            self.zoomTo(float(arg))
        else:
            raise ValueError(f'canvas view: "{value}" is not a view menu row')
