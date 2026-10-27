"""What the pointer over the Editor's roll would do, asked as it moves (a mix-in of SoundBridge, under RollView; PLAN S1,
CANVAS.md §4): the note / hit under it and which part (an end: its length; the body), and with the Draw tool on empty
space, the note or hit a click would make there (`ghost`: the same snap, key lock and Note ▾ length the click uses), so
the screen shows it faintly before the click. One answer per move, from the roll as the screen has it (no document
walk); the screen moves one small item with it.
"""
from __future__ import annotations

from fractions import Fraction

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_core import RostrumError
from rostrum_sound.doc import chords, keys as K, meter, tempo
from rostrum_sound.doc import select_time as ST

from . import drum_steps as D, key_lock, moves, pick, timing

FOLLOWED = ("Paste", "Duplicate")      # a step that makes notes the person didn't place by hand: the roll shows them
PITCHED = ("Change Pitch", "Pitch ", "Transpose")   # a typed or keyed pitch on the selected notes: the roll goes to where they are now
MARGIN = 0.08                         # of the view's width, kept clear round what it slides to show
END_PX = 6.0         # a note's end handle: its last 6 px (RollInput.snapPx)


def length_words(beats: float, bar: float) -> str:
    """A note's length as people say it: "1/8", "3/16", "1 bar", "2 bars 1/4"; a free length in beats ("1.37 beats")."""
    beats = max(0.0, beats)
    whole, rest = divmod(beats + 1e-6, bar)
    rest = max(0.0, rest - 1e-6)
    out = [f"{int(whole)} bar{'s' if whole != 1 else ''}"] if whole >= 1 else []
    if rest > 1e-3:
        f = Fraction(rest / 4).limit_denominator(96)
        if abs(float(f) * 4 - rest) > 1e-3 or f.denominator > 96:
            return f"{beats:.2f} beats"
        out.append(f"{f.numerator}/{f.denominator}")
    return " ".join(out) or "0"


class RollHover:
    rollShow = Signal(float, float, "QVariantList")     # Paste / Duplicate made these on the roll: its time span, its keys or drum rows

    def _roll_follow(self):
        """A Paste or Duplicate (Ctrl+V, Ctrl+D) put notes or hits on the roll's track: the view slides just enough in time
        to show them (not at all when they are in view already) and the roll is told their span (`rollShow`: it slides
        up or down the same way and flashes them once). Its undo and redo move nothing."""
        hist = self.doc.history.changes
        c = hist[-1] if hist else None
        if c is None or not c.original or c.seq <= self.__dict__.get("_followed", 0) or not c.label.startswith(FOLLOWED + PITCHED):
            return
        self.__dict__["_followed"] = c.seq
        by, drums = self.__dict__.get("_roll_by", {}), self._view["roll"].get("drums") or []
        if c.label.startswith(PITCHED):      # the notes it moved (still selected): the roll follows them to their new keys
            made = [by[i] for i in self._picks.ids if i in by and by[i]["type"] == "note"]
        else:
            made = [by[i] for i in ST.inserted(c) if i in by and by[i]["type"] in ("note", "hit")]
        if not made:
            return
        t0, t1 = min(b["t"] for b in made), max(b["t"] + b.get("dur", 0.0) for b in made)
        rows = sorted({k for b in made for k in b["keys"]} if made[0]["type"] == "note"
                      else {drums.index(b["drum"]) for b in made if b["drum"] in drums})
        v = self._zoom
        start, span = v.start, v.span
        if not v.fit and (t0 < start or t1 > start + span):
            pad = span * MARGIN
            self._tv.setStart(t0 - pad if t1 - t0 > span - 2 * pad or t0 < start else t1 + pad - span)
        self.rollShow.emit(t0, t1, rows)

    def _alt_watch(self):
        if "_alt" not in self.__dict__:
            from .roll_keys import AltWatch
            self.__dict__["_alt"] = AltWatch(self)
        return self.__dict__["_alt"]

    altWatch = Property(QObject, _alt_watch, constant=True)     # Alt's changes with the pointer still (roll_keys.py)

    @Slot(float, float, float, float, bool, result="QVariantMap")
    def rollHover(self, t, row, tol, px, draw):
        """The pointer at `t` seconds on roll row `row` (a key, or a drum row's index), `tol`: how near a block counts (on
        the drum rows, how wide the diamond is at the pointer's height: <0 off it), `px`: one screen pixel in seconds.
        {"id", "part" ("length" / "noteStart" / "body"), "t", "dur", "keys", "row"} for the block under it, else with
        `draw`: {"ghost": {"t", "end", "keys" | "row"}} where a click would put a note or a hit; {} for nothing."""
        roll = self._view.get("roll") or {}
        kind = roll.get("kind")
        if kind not in ("notes", "drums") or not self._track:
            return {}
        if kind == "notes":
            h = self.rollHandleAt(t, row, px * END_PX)
            if h.get("id"):
                return self._hovered(h["id"], h["handle"])
        under = pick.roll_at(roll, t, row, tol)
        if under:
            return self._hovered(under, "body")
        if not draw:
            return {}
        root, grid = self.doc.data, self._grid_now
        if kind == "drums":
            i, drums = int(round(row)), roll.get("drums") or []
            if not 0 <= i < len(drums):
                return {}
            at = D.cell_of(t, root, grid, px)
            if any(b["type"] == "hit" and b["drum"] == drums[i] and abs(b["t"] - at) <= D.SAME for b in roll.get("blocks", [])):
                return {}                  # a click there adds nothing (the step has its hit)
            return {"ghost": {"t": at, "end": at, "row": i}}
        at = timing.snap(t, root, False, grid, "cell", px)
        key = int(round(row))
        key = key_lock.snapped(root, at, key) if self.keepInKey else key
        end = tempo.seconds_at(root, timing.beat(at, root) + self._draw_beats(timing.beat(t, root)))
        return {"ghost": {"t": at, "end": end, "keys": self._stamped(key, at, root)}}

    def _stamped(self, key, at, root) -> list[int]:
        """The keys a Draw click stamps on `key` (Note ▾ › Draw: a single note, or a chord shape: note.chord's tones in
        root position, the clicked key lowest); only the key when the shape has no chord there (the click says why)."""
        shape = self.drawChord
        if not shape:
            return [key]
        try:
            return [m for m in chords.shape_tones(key, shape, K.key_for(root, at)) if 0 <= m <= 127] or [key]
        except RostrumError:
            return [key]

    def _hovered(self, item_id, part):
        b = self.__dict__.get("_roll_by", {}).get(item_id)
        if b is None:
            return {"id": item_id, "part": part}
        out = {"id": item_id, "part": part, "t": b["t"], "dur": b.get("dur", 0.0)}
        if b["type"] == "note":
            out["keys"] = list(b["keys"])
        elif b["type"] == "hit":
            drums = self._view["roll"].get("drums") or []
            out["row"] = drums.index(b["drum"]) if b["drum"] in drums else -1
        return out

    @Slot(str)
    def eraseNote(self, item_id):
        """Draw with Alt, a click on a note: that note goes (one step), whatever is selected."""
        if self.doc.has(item_id) and self.doc.item(item_id)["type"] in ("note", "hit"):
            kind = self.doc.item(item_id)["type"]
            self._guard(lambda: self._apply(moves.remove_calls(self.doc, kind, [item_id]), f"Erase {kind}"))

    @Slot(str, "QVariant", result=str)
    def lengthWords(self, item_id, _blocks=None):
        """The chip beside a note's end being dragged: its length now ("1/8"). `_blocks`: the screen's list, so the
        words follow each step of the drag."""
        b = self.__dict__.get("_roll_by", {}).get(item_id)
        if b is None or b["type"] != "note":
            return ""
        root = self.doc.data
        a = timing.beat(b["t"], root)
        return length_words(timing.beat(b["t"] + b["dur"], root) - a, meter.seg_at(root, a).bar)

