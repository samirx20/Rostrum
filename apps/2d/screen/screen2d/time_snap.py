"""Snapping in time, the ONE source (UX_SPEC 6.2, INTERACTION 1.11): a key drag, a key stretch and a bar drag all ask
here where a time lands. Targets, strongest first: shared markers, the playhead, other layers' bar ends and keys (of
every layer shown), the music's bar starts, then its beats, when the project has a tempo; within 6 screen px (the drag passes that as
seconds; 0 = Ctrl held: free), else the nearest whole frame. Each answer says what it caught, so a marker drop can
tie (bar_drag.py) and the drag label can name it ("+6 f · drop").

`TimeSnap` (backend.timeSnap) holds what a running time drag shows: the label beside the dragged edge or key (its
time and its layer's row, so it sits right for the mouse, the steps and agents alike: qml/DragLabel.qml) and the
time it caught (the timeline's magenta line, qml/SnapLine.qml). Screen state only, cleared when the drag ends.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum2d import fields as F
from rostrum2d.retime import END_OF_COMP

from . import beat_words

RANK = {"marker": 0, "playhead": 1, "edge": 2, "key": 2, "measure": 3, "beat": 4}   # INTERACTION 1.11; bars over beats (UX_SPEC 3.28)


@dataclass(frozen=True)
class Target:
    kind: str           # marker | playhead | edge (a layer bar's start / end) | key | measure (a music bar) | beat
    name: str           # what the label says ("drop", "playhead", "Title start", "key · Title", "bar 2", "beat 5")
    t: float            # composition seconds


def _layer_keys(item: dict):
    yield from item.get("keys", [])
    for part in ("effects", "masks"):
        for child in item.get(part, []):
            yield from child.get("keys", [])


def targets(bridge, skip_keys=(), skip_layers=(), carried=()) -> list[Target]:
    """Everything a time drag may catch now, minus what the drag itself moves (it never snaps to itself): `skip_keys`,
    the bar ends of `skip_layers` (a trim), and all of `carried` with what it holds (a bar moved in time)."""
    out = [Target("marker", name, at) for name, at in bridge.times().items()]
    out.append(Target("playhead", "playhead", bridge.time))
    skip_keys, skip_layers, carried = set(skip_keys), set(skip_layers), set(carried)

    def walk(layers):
        for lay in layers:
            if lay.get("hidden") or lay.get("type") not in F.LAYERS or lay["id"] in carried:
                continue
            name = bridge.label_of(lay)
            if lay["id"] not in skip_layers:
                out.append(Target("edge", f"{name} start", lay.get("start", 0.0)))
                if lay.get("end", END_OF_COMP) < END_OF_COMP:
                    out.append(Target("edge", f"{name} end", lay["end"]))
            out.extend(Target("key", f"key · {name}", k["t"]) for k in _layer_keys(lay)
                       if k["id"] not in skip_keys and isinstance(k["t"], (int, float)))
            walk(lay.get("layers", []))
    walk(bridge.placed().get("layers", []))
    sound = getattr(bridge, "soundtrack", None)          # the project's music (member "sound": soundtrack*.py)
    bars = sound.bar_times() if sound is not None else []
    beats = sound.beat_times() if sound is not None else []
    fps = bridge.comp()["fps"]                           # their names are the one beat wording (beat_words.py)
    out.extend(Target("measure", beat_words.words(t, beats, bars, fps) or f"bar {n + 1}", t) for n, t in enumerate(bars))
    out.extend(Target("beat", beat_words.words(t, beats, bars, fps) or f"beat {n + 1}", t) for n, t in enumerate(beats)
               if not any(abs(t - b) < 1e-6 for b in bars))
    return out


def snap(t: float, found: list[Target], within: float, fps: float) -> tuple[float, Target | None]:
    """Where `t` (composition seconds) lands: on the strongest target within `within` seconds (nearest among equals),
    else on the nearest whole frame."""
    near = [g for g in found if abs(g.t - t) <= within] if within > 0 else []
    if near:
        best = min(near, key=lambda g: (RANK[g.kind], abs(g.t - t)))
        return best.t, best
    return round(t * fps) / fps, None


def label(dt: float, fps: float, caught: Target | None = None) -> str:
    """The pointer's label: the offset in whole frames ("+6 f", "−3 f", "0 f"), and what it caught."""
    n = round(dt * fps)
    words = f"+{n} f" if n > 0 else f"−{-n} f" if n < 0 else "0 f"
    return f"{words} · {caught.name}" if caught is not None else words


class TimeSnap(QObject):
    """A running time drag: the label's words, where it sits (the dragged thing's time and layer row), what it caught."""
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text, self._t, self._row, self._at = "", 0.0, "", None

    text = Property(str, lambda self: self._text, notify=changed)
    t = Property(float, lambda self: self._t, notify=changed)                          # the dragged edge / key, seconds
    row = Property(str, lambda self: self._row, notify=changed)                        # its layer (the label's row)
    caught = Property(bool, lambda self: self._at is not None, notify=changed)        # snapped now
    caughtT = Property(float, lambda self: self._at or 0.0, notify=changed)           # where (composition seconds)

    def show(self, dt: float, fps: float, caught: Target | None, t: float, row: str):
        """A time drag moved: `dt` seconds from where it began, the dragged thing now at `t` on layer `row`."""
        now = (label(dt, fps, caught), caught.t if caught is not None else None, t, row)
        if now != (self._text, self._at, self._t, self._row):
            self._text, self._at, self._t, self._row = now
            self.changed.emit()

    def clear(self):
        if self._text or self._at is not None:
            self._text, self._at = "", None
            self.changed.emit()
