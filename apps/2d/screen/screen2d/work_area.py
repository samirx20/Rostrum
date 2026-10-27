"""The time ruler's right-click menu and the work area it sets (backend.workArea; qml/RulerMenu.qml draws both).

The menu at a time t on the ruler: Add a marker here… (a name field, then one marker operation; only in a project
folder, where markers live), Work area starts here / ends here (and Clear the work area once there is one), Go to here,
Go to the start / end. The work area is a span of the scene the person works on, as in After Effects: it shows as a band
on the ruler (drag it to change it, double-click it to clear it) and the Export sheet offers it as a time range
(exporter.py). Screen state per scene, kept while the window is open; never in the document, so never undone.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot


def _s(t: float) -> str:
    return f"{t:.2f} s"


class WorkArea(QObject):
    changed = Signal()
    named = Signal(str)                 # a marker just added at the playhead (the flag button, M): QML opens its name

    def __init__(self, bridge):
        super().__init__(bridge)
        self.b = bridge
        self._spans: dict[str, tuple[float, float]] = {}      # {scene id: (start, end)} in seconds
        self._known: set | None = None                        # the marker ids last seen (None: not read yet)
        self._quiet = False                                   # addMarker says its own words

    def marks_changed(self):
        """The markers changed: one new marker at the playhead (the flag button, M) is said in the top bar and its
        name field opens on the ruler, so "Marker 1" is never added without a word."""
        rows = self.b.marks.rows()
        ids = {m["id"] for m in rows}
        new, self._known = (ids - self._known if self._known is not None else set()), ids
        if len(new) != 1 or self._quiet:
            return
        m = next(r for r in rows if r["id"] in new)
        fps = self._comp()["fps"]
        if round(m["at"] * fps) == round(self.b.time * fps):
            self.b._set_status(f'Added "{m["name"]}" at {_s(m["at"])}: type a name for it, or Esc to keep this one')
            self.named.emit(m["id"])

    def _comp(self):
        return self.b.comp()

    def span(self) -> tuple[float, float] | None:
        """(start, end) of the shown scene's work area, inside its length; None when it has none."""
        got = self._spans.get(self.b.comp_id)
        if not got:
            return None
        d = float(self._comp()["duration"])
        a, b = max(0.0, min(got[0], d)), max(0.0, min(got[1], d))
        return (a, b) if b > a else None

    @Property("QVariant", notify=changed)
    def range(self):
        s = self.span()
        return {"start": s[0], "end": s[1]} if s else None

    def _frame(self, t: float) -> float:
        fps = self._comp()["fps"]
        return round(max(0.0, min(float(t), float(self._comp()["duration"]))) * fps) / fps

    def _put(self, a: float, b: float, words: str):
        self._spans[self.b.comp_id] = (a, b)
        self.changed.emit()
        self.b._set_status(f"{words}: work area {_s(a)} – {_s(b)} (Export can use it; drag its band on the ruler to change it)")

    @Slot(float, float)
    def set(self, a, b):
        """The band dragged (Ruler.rangeSet): the new span."""
        a, b = self._frame(min(a, b)), self._frame(max(a, b))
        if b > a:
            self._put(a, b, "Set")

    @Slot(float)
    def setStart(self, t):
        now, t = self.span(), self._frame(t)
        end = now[1] if now and now[1] > t else float(self._comp()["duration"])
        if end > t:
            self._put(t, end, f"Starts at {_s(t)}")

    @Slot(float)
    def setEnd(self, t):
        now, t = self.span(), self._frame(t)
        start = now[0] if now and now[0] < t else 0.0
        if t > start:
            self._put(start, t, f"Ends at {_s(t)}")

    @Slot()
    def clear(self):
        if self._spans.pop(self.b.comp_id, None) is not None:
            self.changed.emit()
            self.b._set_status("Cleared the work area")

    # ---- the ruler's right-click ------------------------------------------------------------------------------
    @Slot(float, result="QVariantList")
    def menu(self, t):
        """The rows at time t (seconds), only what applies (no marker rows outside a project folder)."""
        t, d, now = self._frame(t), float(self._comp()["duration"]), self.span()
        rows = []
        if self.b.marks is not None and self.b.marks.available:
            rows.append({"value": "marker", "label": "Add a marker here…", "keys": "", "group": "mark"})
        if t < d:
            rows.append({"value": "start", "label": "Work area starts here", "keys": "", "group": "work"})
        if t > 0:
            rows.append({"value": "end", "label": "Work area ends here", "keys": "", "group": "work"})
        if now:
            rows.append({"value": "clear", "label": "Clear the work area", "keys": "", "group": "work"})
        rows.append({"value": "here", "label": f"Go to {_s(t)}", "keys": "", "group": "go"})
        rows += [{"value": "first", "label": "Go to the start", "keys": "Home", "group": "go"},
                 {"value": "last", "label": "Go to the end", "keys": "End", "group": "go"}]
        return rows

    @Slot(str, float)
    def choose(self, value, t):
        """A row picked ("marker" is QML's: it opens the ruler's name field at t, then addMarker)."""
        d = float(self._comp()["duration"])
        if value == "start":
            self.setStart(t)
        elif value == "end":
            self.setEnd(t)
        elif value == "clear":
            self.clear()
        elif value in ("here", "first", "last"):
            self.b.setTime({"here": t, "first": 0.0, "last": d}[value])

    @Slot(str, float)
    def addMarker(self, name, at):
        """The ruler's name field said yes: one marker with that name at `at` (one change, undone as one)."""
        marks = self.b.marks
        args = {"name": name, "at": round(max(at, 0.0), 6), **({"owner": marks.owner} if marks.owner else {})}
        self._quiet = True
        try:
            done = marks._edit([{"op": "marker.add", "args": args}], "Add marker")
        finally:
            self._quiet = False
        if done:
            self.b._set_status(f'Added the marker "{name}" at {_s(at)}')
