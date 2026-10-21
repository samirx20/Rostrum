"""The master's loudness readout, live: the short-term loudness (LUFS-S) and the true peak at the playhead, read from
the series the engine measured on the render that plays (preview ≡ export), the curve with the delivery target line,
and the pass / miss line. Exposed to QML as `mixer.loudness`. The target and its line show only while the master's
normalize is on (rule of individuality); choosing a delivery target is one `master.set`.

`series`: `shortTerm[k]` is the 3 s window ending at `k * hop + window`; `truePeak[k]` covers the hop starting at `k * hop`.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from . import delivery, strips

FLOOR = -120          # the engine's value for digital silence


def at(values: list, t: float, hop: float, offset: float = 0.0):
    """values[k] for the hop holding time `t - offset`, or None when that is before the first or after the last."""
    k = int((t - offset) // hop) if t >= offset else -1
    return values[k] if 0 <= k < len(values) else None


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
        self._now: dict = {"shortTerm": None, "peak": None}
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

    @Property("QVariantMap", notify=changed)
    def target(self):
        """{shown, lufs, peak, label, verdict}: the master's own target; `verdict` is {ok, text} once a render exists."""
        m = self.bridge.doc.item(strips.MASTER)
        if not m.get("normalize"):
            return {"shown": False}
        return {"shown": True, "lufs": m.get("loudness", -16), "peak": m.get("truePeak", -1), "label": delivery.label_of(m),
                "key": delivery.key_of(m), "verdict": delivery.verdict(m, self.bridge.lastRender or {})}

    @Property("QVariantList", constant=True)
    def choices(self):
        return delivery.choices()

    # ---- the one edit ----------------------------------------------------------------------------------------
    @Slot(str, result=bool)
    def choose(self, key):
        """master.set: loudness and true peak of that delivery target (one change)."""
        return self.bridge._guard(lambda: self.bridge._apply([delivery.call(key)], "Set delivery target"))

    # ---- inside ----------------------------------------------------------------------------------------------
    def _render(self):
        self._series = dict((self.bridge.lastRender or {}).get("series") or {})
        self._top = running_max(self._series.get("truePeak") or [])
        self.changed.emit()
        self._tick(self.bridge.time)

    def _tick(self, *_):
        s, t = self._series, self.bridge.time
        hop, window = s.get("hop", 0.1), s.get("shortTermWindow", 3.0)
        st = at(s.get("shortTerm") or [], t, hop, window)
        peak = at(self._top, t, hop)
        now = {"shortTerm": None if st is None or st <= FLOOR else st, "peak": None if peak is None or peak <= FLOOR else peak}
        if now != self._now:
            self._now = now
            self.nowChanged.emit()
