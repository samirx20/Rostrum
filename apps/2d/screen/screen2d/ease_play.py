"""An ease picked plays once (UX_SPEC 3.18 › Feedback): picking an ease in the key bar (Ease ▾, a key's right-click,
F9 …) plays, on the canvas, the stretch that ease shapes — from the picked key to the next one (the earliest picked
to the latest's next; a last key: from the key before it) — once, then the playhead goes back to where it was. So
the feel shows at once. Screen state only: nothing changes in the document, and a drag (the small curve, Bounce /
Speed) never plays. The key bar's ⋯ turns it off (`on`). Offered to QML as `backend.easePlay`.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_core.keys import keys_of


class EasePlay(QObject):
    changed = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._on = bridge, True

    @Property(bool, notify=changed)
    def on(self):
        return self._on

    @Slot(bool)
    def setOn(self, on):
        self._on = bool(on)
        self.changed.emit()

    def span(self, ids) -> tuple[float, float] | None:
        """(from, to) composition seconds the picked keys' eases shape; None when there is no stretch."""
        spans = []
        for kid in ids:
            key = self.b.placed_item(kid)
            row = keys_of(self.b.placed_item(self.b.doc.parent_of(kid)[0]), key["prop"])
            at = next((n for n, k in enumerate(row) if k["id"] == kid), None)
            if at is None or len(row) < 2:
                continue
            a, z = (row[at], row[at + 1]) if at + 1 < len(row) else (row[at - 1], row[at])
            spans.append((a["t"], z["t"]))
        if not spans:
            return None
        dur = self.b.comp()["duration"]
        t0, t1 = max(0.0, min(s[0] for s in spans)), min(dur, max(s[1] for s in spans))
        return (t0, t1) if t1 > t0 else None

    def play(self, ids) -> bool:
        """Play the stretch once and come back (playback.once). False when off, playing (by hand), or no stretch. A
        second pick while one plays starts it again, still coming back to where the first began."""
        once = self.b.play._once
        span = self.span(ids) if self._on and (once or not self.b.play.playing) else None
        if span is None:
            return False
        self.b.play.once(span[0], span[1], once[1] if once else self.b.time)
        return True
