"""The master's loudness readout, live: the short-term loudness (LUFS-S) and the true peak at the playhead, read from
the series the engine measured on the render that plays (preview ≡ export), the curve with the delivery target line,
and the pass / miss line. Exposed to QML as `mixer.loudness`. The delivery chooser shows while one of its fields
applies (delivery.applying, by their valid_when); the target line only while the loudness target does (Normalize on).
Choosing a delivery target is one `master.set`.

`series`: `shortTerm[k]` is the 3 s window ending at `k * hop + window`; `truePeak[k]` covers the hop starting at `k * hop`;
`momentary[k]` is the 400 ms block ending at `k * hop + 0.4` (BS.1770's gating blocks: the integrated loudness so far
is their gated mean, `integrated`).
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from . import delivery, strips

FLOOR = -120          # the engine's value for digital silence


def at(values: list, t: float, hop: float, offset: float = 0.0):
    """values[k] for the hop holding time `t - offset`, or None when that is before the first or after the last."""
    k = int((t - offset) // hop) if t >= offset else -1
    return values[k] if 0 <= k < len(values) else None


def integrated(momentary: list, n: int):
    """BS.1770 integrated loudness of the first `n` 400 ms blocks (LUFS each): the mean power of the blocks above
    −70 LUFS, then of those above that mean − 10 LU. None when no block passes the first gate (silence so far)."""
    import numpy as np
    blocks = np.asarray(momentary[:n], dtype=float)
    power = 10 ** ((blocks + 0.691) / 10)
    loud = power[blocks > -70]
    if not len(loud):
        return None
    gate = -0.691 + 10 * np.log10(loud.mean()) - 10
    kept = power[(blocks > -70) & (blocks > gate)]
    return float(-0.691 + 10 * np.log10(kept.mean()))


def running_max(values: list) -> list:
    out, top = [], float(FLOOR)
    for v in values:
        top = max(top, v)
        out.append(top)
    return out


class LoudnessMeter(QObject):
    changed = Signal()        # a new render, or the master changed
    nowChanged = Signal()     # the playhead moved

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self._series: dict = {}
        self._top: list = []          # running maximum of the true-peak series
        self._now: dict = {"shortTerm": None, "peak": None, "integrated": None}
        self._upto: tuple = (-1, None)    # (blocks counted, their integrated loudness): counted again only when it grows
        bridge.renderChanged.connect(self._render)
        bridge.timeChanged.connect(self._tick)
        bridge.docChanged.connect(self.changed)
        self._render()

    # ---- reads -----------------------------------------------------------------------------------------------
    @Property("QVariantList", notify=changed)
    def curve(self):
        return list(self._series.get("shortTerm") or [])

    @Property("QVariantMap", notify=changed)
    def axis(self):
        """{hop, window, seconds}: where curve[k] sits on the time axis (it ends at k * hop + window)."""
        s = self._series
        return {"hop": s.get("hop", 0.1), "window": s.get("shortTermWindow", 3.0),
                "seconds": float((self.bridge.lastRender or {}).get("seconds") or 0)}

    @Property("QVariant", notify=nowChanged)
    def shortTerm(self):
        return self._now["shortTerm"]

    @Property("QVariant", notify=nowChanged)
    def peakNow(self):
        return self._now["peak"]

    @Property("QVariant", notify=nowChanged)
    def integratedNow(self):
        """Integrated loudness from the start to the playhead (gated over the render's 400 ms blocks); None before
        the first block ends, or when the render carries no blocks."""
        return self._now["integrated"]

    @Property("QVariantMap", notify=changed)
    def target(self):
        """{shown, lufs, peak, label, verdict}: the master's own target; `verdict` is {ok, text} once a render exists."""
        m, fields = self._fields()
        if not fields:
            return {"shown": False}
        return {"shown": True, "lufs": m.get("loudness", -16) if "loudness" in fields else None,
                "peak": m.get("truePeak", -1), "label": delivery.label_of(m, fields), "key": delivery.key_of(m, fields),
                "choices": delivery.choices(fields), "verdict": delivery.verdict(m, self.bridge.lastRender or {}, fields)}

    # ---- the one edit ----------------------------------------------------------------------------------------
    @Slot(str, result=bool)
    def choose(self, key):
        """master.set: that delivery target's numbers for the fields that apply now (one change)."""
        return self.bridge._guard(lambda: self.bridge._apply([delivery.call(key, self._fields()[1])],
                                                             "Set delivery target"))

    # ---- inside ----------------------------------------------------------------------------------------------
    def _fields(self) -> tuple[dict, list[str]]:
        doc = self.bridge.doc
        m = doc.item(strips.MASTER)
        return m, delivery.applying(doc.kind.registry.field_op("master"), m, doc.kind.facts(m, doc))

    def _integrated(self, t):
        s = self._series
        blocks = s.get("momentary") or []
        n = min(len(blocks), int((t - s.get("momentaryWindow", 0.4)) // s.get("hop", 0.1)) + 1)
        if n != self._upto[0]:
            self._upto = (n, integrated(blocks, n) if n > 0 else None)
        return self._upto[1]

    def _render(self):
        self._series = dict((self.bridge.lastRender or {}).get("series") or {})
        self._upto = (-1, None)
        self._top = running_max(self._series.get("truePeak") or [])
        self.changed.emit()
        self._tick(self.bridge.time)

    def _tick(self, *_):
        s, t = self._series, self.bridge.time
        hop, window = s.get("hop", 0.1), s.get("shortTermWindow", 3.0)
        st = at(s.get("shortTerm") or [], t, hop, window)
        peak = at(self._top, t, hop)
        now = {"shortTerm": None if st is None or st <= FLOOR else st, "peak": None if peak is None or peak <= FLOOR else peak,
               "integrated": self._integrated(t)}
        if now != self._now:
            self._now = now
            self.nowChanged.emit()
