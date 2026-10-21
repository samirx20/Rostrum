"""How the next take is made (screen state, not a document edit): count-in, punch in / out, hearing the input, which
MIDI keyboard, quantize. `controls` is built from ROWS, each with its "valid when": a row shows only while it can be
used (count-in bars only with count-in on, the punch range only with punch on, hearing the input only while the
microphone is open, the keyboard rows only on a notes or drum track), most important first. The take panel
(qml/RecordSetup.qml) draws exactly these rows. The punch range is dragged on the ruler (`setPunch`, BarRuler.qml).
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_sound.doc import tempo

from .timeline import kind_of
from .timing import snap

GRIDS = [{"value": "1", "label": "Beat"}, {"value": "0.5", "label": "1/8 note"}, {"value": "0.25", "label": "1/16 note"}]
KEYS_KINDS = ("notes", "drums")


def _keys(s):
    return s.kind in KEYS_KINDS


def _mic_line(s):
    mic = s.mic or {}
    delay = mic.get("inputOffsetMs")
    return (mic.get("name") or "Microphone") + " open: " + (f"its delay ({delay:.0f} ms) is taken off each take" if delay is not None else
                                  "its delay is not measured yet (rostrum-sound play --calibrate)")


# (key, kind, label (str, or setup → str), valid when (setup → bool), extra). Order = importance.
ROWS = [
    ("countIn", "toggle", "Count-in", lambda s: True, {}),
    ("countInBars", "number", "Bars", lambda s: s.values["countIn"], {"from": 1, "to": 8, "step": 1}),
    ("punch", "toggle", "Punch in", lambda s: True, {}),
    ("punchRange", "text", lambda s: f"{s.values['punchIn']:.2f} – {s.values['punchOut']:.2f} s · drag on the ruler",
     lambda s: s.values["punch"], {}),
    ("hear", "toggle", "Hear input", lambda s: bool(s.mic), {}),
    ("hearGain", "number", "Volume", lambda s: bool(s.mic) and s.values["hear"], {"from": 0, "to": 2, "step": 0.05}),
    ("micLine", "text", _mic_line, lambda s: bool(s.mic), {}),
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
                       "hear": False, "hearGain": 1.0, "midiDevice": "0", "quantize": False, "quantizeGrid": "0.25"}
        self.armed, self.devices, self.recording, self.mic, self._open = "", [], False, None, False
        self.on_set = None                   # recording.py: what a change means for the engine (hear, keyboard)

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
                row = {"key": key, "kind": kind, "label": label(self) if callable(label) else label,
                       "value": self.values.get(key), **extra}
                if key == "midiDevice":
                    row["options"] = [{"value": str(i), "label": n} for i, n in enumerate(self.devices)]
                out.append(row)
        return out

    @Property("QVariantList", notify=changed)
    def punchRange(self):
        """[in, out] seconds while a track is armed with punch on (the ruler and the rows shade it); [] otherwise."""
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
            t = snap(self.bridge.time, self.bridge.doc.data, False)     # a fresh range: from the playhead, two bars
            self.values["punchIn"], self.values["punchOut"] = t, round(t + 2 * self.bar_seconds(t), 6)
        self.values[key] = int(value) if key == "countInBars" else float(value) if key == "hearGain" else value
        if self.on_set:
            self.on_set(key)
        self.changed.emit()

    @Slot(float, float, bool)
    def setPunch(self, a, b, free=False):
        """The punch range from a drag on the ruler (either way round), snapped to a quarter beat unless free;
        never shorter than a quarter beat."""
        root = self.bridge.doc.data
        a, b = sorted((snap(a, root, free), snap(b, root, free)))
        if b - a < 1e-3:
            b = round(a + tempo.beat_seconds(root, a) / 4, 6)
        self.values.update(punch=True, punchIn=a, punchOut=b)
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
