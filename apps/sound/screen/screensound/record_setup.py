"""How the next take is made (screen state, not a document edit): count-in, punch in / out, checking the input level,
which MIDI keyboard, quantize. `controls` is built from ROWS, each with its "valid when": a row shows only while it
can be used (count-in bars only with count-in on, the punch times only with punch on, the keyboard rows only on a
notes or drum track), most important first. The take panel (qml/RecordSetup.qml) draws exactly these rows.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_sound.doc import tempo

from .timeline import kind_of

GRIDS = [{"value": "1", "label": "Beat"}, {"value": "0.5", "label": "1/8 note"}, {"value": "0.25", "label": "1/16 note"}]
KEYS_KINDS = ("notes", "drums")


def _keys(s):
    return s.kind in KEYS_KINDS


# (key, kind, label, valid when (setup → bool), extra). Order = importance.
ROWS = [
    ("countIn", "toggle", "Count-in", lambda s: True, {}),
    ("countInBars", "number", "Bars", lambda s: s.values["countIn"], {"from": 1, "to": 8, "step": 1}),
    ("punch", "toggle", "Punch in", lambda s: True, {}),
    ("punchIn", "number", "From", lambda s: s.values["punch"], {"from": 0, "to": 3600, "step": 0.01, "unit": " s"}),
    ("punchOut", "number", "To", lambda s: s.values["punch"], {"from": 0, "to": 3600, "step": 0.01, "unit": " s"}),
    ("checkInput", "toggle", "Input level", lambda s: not s.recording, {}),
    ("midiDevice", "choice", "Keyboard", lambda s: _keys(s) and bool(s.devices), {}),
    ("noKeyboard", "text", "No MIDI keyboard found", lambda s: _keys(s) and not s.devices, {}),
    ("quantize", "toggle", "Quantize", lambda s: _keys(s), {}),
    ("quantizeGrid", "choice", "To", lambda s: _keys(s) and s.values["quantize"], {"options": GRIDS}),
]


class RecordSetup(QObject):
    changed = Signal()
    openChanged = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.values = {"countIn": False, "countInBars": 1, "punch": False, "punchIn": 0.0, "punchOut": 0.0,
                       "checkInput": False, "midiDevice": "0", "quantize": False, "quantizeGrid": "0.25"}
        self.armed, self.devices, self.recording, self._open = "", [], False, False
        self.on_check = None                 # recording.py: start / stop the input level check

    @property
    def kind(self) -> str:
        doc = self.bridge.doc
        return kind_of(doc.item(self.armed)) if self.armed and doc.has(self.armed) else ""

    def refresh(self, **state):
        for k, v in state.items():
            setattr(self, k, v)
        self.changed.emit()

    @Property("QVariantList", notify=changed)
    def controls(self):
        out = []
        for key, kind, label, valid, extra in ROWS:
            if valid(self):
                row = {"key": key, "kind": kind, "label": label, "value": self.values.get(key), **extra}
                if key == "midiDevice":
                    row["options"] = [{"value": str(i), "label": n} for i, n in enumerate(self.devices)]
                out.append(row)
        return out

    @Property("QVariantList", notify=changed)
    def punchRange(self):
        """[in, out] seconds while a track is armed with punch on (the timeline shades it); [] otherwise."""
        p = self.punch()
        return list(p) if p and self.armed else []

    @Property(bool, notify=openChanged)
    def open(self):
        return self._open

    @Slot(bool)
    def setOpen(self, on):
        if on != self._open:
            self._open = on
            self.openChanged.emit()

    @Slot(str, "QVariant")
    def set(self, key, value):
        if key == "punch" and value and self.values["punchOut"] <= self.values["punchIn"]:
            t = self.bridge.time                  # a fresh range: from the playhead, two bars long
            self.values["punchIn"], self.values["punchOut"] = round(t, 2), round(t + 2 * self.bar_seconds(t), 2)
        if key == "punchIn":
            value = min(float(value), self.values["punchOut"])
        if key == "punchOut":
            value = max(float(value), self.values["punchIn"])
        self.values[key] = int(value) if key == "countInBars" else value
        if key == "checkInput" and self.on_check:
            self.on_check(bool(value))
        self.changed.emit()

    # ---- what a take reads ----------------------------------------------------------------------------------------
    def bar_seconds(self, t: float) -> float:
        root = self.bridge.doc.data
        return tempo.beat_seconds(root, t) * int(root.get("beatsPerBar", 4))

    def count_in(self, t: float) -> tuple[int, float]:
        """(clicks, seconds between them) before a take starting at `t`; (0, …) when count-in is off."""
        root = self.bridge.doc.data
        beats = int(root.get("beatsPerBar", 4)) * self.values["countInBars"] if self.values["countIn"] else 0
        return beats, tempo.beat_seconds(root, t)

    def punch(self):
        return (self.values["punchIn"], self.values["punchOut"]) if self.values["punch"] else None

    def start_at(self, t: float) -> float:
        """Where playback starts: the playhead, or a bar before the punch-in when the playhead is past it."""
        p = self.punch()
        return max(0.0, p[0] - self.bar_seconds(p[0])) if p and t > p[0] - 0.05 else t

    def device(self) -> int:
        return int(self.values["midiDevice"])

    def grid(self) -> float | None:
        return float(self.values["quantizeGrid"]) if self.values["quantize"] else None
