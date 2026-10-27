"""Times and pitches as the screen reads and writes them. No Qt.

Reading goes through the document's own `times` (seconds, `{"beat": n}`, `"#drop+0.5"`). Writing keeps the form
the item already used: a note placed in beats is moved in beats, one placed on a marker stays on that marker
(`"#drop+0.25"`), seconds stay seconds. A drag snaps to the grid unless it is free (Ctrl) or Snap is off.

A `Grid` is a window's grid setting (Grid ▾ and Snap in the arrangement's header; screen state, never saved): the
bridge holds one and passes it to every snap (drags, ends, the ruler's range, Draw, nudges); without one, the
default (Auto, Snap on) is used. Auto follows the zoom: the finest step at least MIN_PX wide on screen.

One snap, three ways (`snap(..., how=)`): a drag, a nudge, a note's end and both edges of a time range go to the
NEAREST line; a click that makes something (a drum hit, an automation point, a paste) takes the CELL under the
pointer, the line at or before it; a note drawn on the roll (Draw click, double-click) goes to the nearest line, a bar
line within PULL_PX first (DRAW: at 1/16 a cell is ~4 px, so the cell rule put a click 4 px past the bar a 16th late
while the person aimed at the bar; beat lines don't pull there, so the 16ths beside a beat stay reachable). `px` is one screen pixel in seconds: the screen draws a line on its nearest whole pixel, so a
pointer on that pixel is on the line (a press exactly on a drawn line gives that line's time, a pixel before it the
cell before).

Strong lines pull first: with `px` given, a "nearest" snap within PULL_PX of a bar line takes the bar line, then a
beat line, before the finest grid step. People aim at the bar line they see; a fine step is only 8-16 px wide, so a
release 5 px past the bar was nearer the next step and a range ended one step late (critic r5, r6, r7).

Markers pull before the grid: a window's Grid carries `marks` (its markers and section edges, from the bridge), and
any snap from the screen (`px` given) within the kit's 6 px of one lands on it, for a click that makes something as
for a drag or a range (critic r8: Snap ignored the picture's markers, so a hit aimed at the flash landed a beat late).
The ruler, the arrangement and the Editor all land a pointer through this one rule (`catch`, then the grid).
"""
from __future__ import annotations

import re

from rostrum_sound.doc import keys as K
from rostrum_sound.doc import meter, musical, tempo, times
from rostrum_sound.doc.shift import spb, write_like
from rostrum_gui import snap as kit_snap

SNAP_BEATS = 0.25          # the music map's own snap (tempo / key changes, sections): a quarter beat
PULL_PX = 7.0              # a bar or beat line this near the pointer (screen px) wins over finer grid lines
MIN_PX = 8.0               # Auto: no step narrower than this on screen
EPS = 1e-6                 # beats: a time written as a line's seconds is on that line


class Grid:
    """Grid ▾: "bar", "1/2", "beat" (1/4), "1/8", "1/16", "1/32", "1/8T", "1/16T" (triplets) or "auto" (follows the zoom);
    Snap on / off."""
    STEPS = {"1/2": 2.0, "beat": 1.0, "1/8": 0.5, "1/16": 0.25, "1/32": 0.125, "1/8T": 1 / 3, "1/16T": 1 / 6}
    CHOICES = ["auto", "bar", "1/2", "beat", "1/8", "1/16", "1/32", "1/8T", "1/16T"]

    def __init__(self):
        self.value, self.on, self.auto_beats = "auto", True, 0.25
        self.marks = None        # the window's markers and section edges: marks(skip="") -> [kit Target] (None: none)

    def beats(self, root: dict, at: float = 0.0) -> float:
        """One step in beats at beat `at`; for "bar", that bar's length (`snap` follows each bar's own); "beat" is
        the time signature's count there (an eighth in 6/8)."""
        if self.value == "bar":
            return meter.seg_at(root, at).bar
        if self.value == "beat":
            return meter.count(meter.seg_at(root, at))
        return self.auto_beats if self.value == "auto" else self.STEPS[self.value]

    def follow_zoom(self, span_beats: float, width_px: float, min_px: float = MIN_PX) -> bool:
        """Auto: the finest step at least `min_px` wide when `span_beats` fill `width_px` (1/32 … 4 beats). True when
        it changed."""
        px_per_beat = width_px / max(span_beats, 1e-6)
        b = next((b for b in (0.125, 0.25, 0.5, 1.0, 2.0) if b * px_per_beat >= min_px), 4.0)
        changed, self.auto_beats = b != self.auto_beats, b
        return changed


DEFAULT = Grid()             # never changed: what a caller without a window's grid gets


def step_beats(root: dict, grid: Grid | None = None) -> float:
    """One grid step in beats (nudges, Draw's note length, Ctrl+arrows)."""
    return (grid or DEFAULT).beats(root)


def sec(value, root: dict, where="time") -> float:
    return times.seconds(value, root, where)


def length_sec(value, root: dict, start: float = 0.0, item: dict | None = None) -> float:
    """A length as seconds for a thing starting at `start` seconds (beats through the tempo map; a tied note's
    `"next"` needs the note itself)."""
    return times.length_seconds(value, root, start, item)


def beat(t: float, root: dict) -> float:
    """The beat at `t` seconds (the tempo map)."""
    return tempo.beat_at(root, t)


def lines_around(t: float, root: dict, grid: Grid | None = None) -> tuple[float, float]:
    """(the grid line at or before `t`, the next one), in seconds. Steps count from the bar `t` is in, so the grid
    stays on the bar lines after an odd bar; a bar's last cell ends on the next bar line."""
    grid = grid or DEFAULT
    b = max(0.0, tempo.beat_at(root, max(0.0, t)))
    s = meter.seg_at(root, b)
    bar0 = s.start + ((b - s.start + EPS) // s.bar) * s.bar
    step = s.bar if grid.value == "bar" else grid.beats(root, b)
    lo = bar0 + ((b - bar0 + EPS) // step) * step
    hi = min(lo + step, bar0 + s.bar)
    return tempo.seconds_at(root, lo), tempo.seconds_at(root, hi)


def snap(t: float, root: dict, free: bool, grid: Grid | None = None, how: str = "nearest", px: float = 0.0) -> float:
    """`t` seconds onto `grid` (the window's; through the tempo map), unless free or its Snap is off. `how`:
    "nearest" (drags, ends, nudges, a range's edges), "cell" (a click that makes something: the cell under the
    pointer), "draw" (a Draw click or double-click on the notes: the nearest line, a bar line within PULL_PX first; the
    hover's faint note and its snap line ask the same, so the note lands where they showed). `px`: one screen pixel in
    seconds (0: not from the screen)."""
    grid = grid or DEFAULT
    if free or not grid.on:
        return max(0.0, round(t, 4))
    caught = catch(t, grid, px)
    if caught is not None:
        return max(0.0, round(caught.value, 6))
    if how in ("nearest", "draw"):
        lo, hi = lines_around(t, root, grid)
        at = strong_line(t, root, px * PULL_PX, how == "nearest") if px > 0 else None
        at = at if at is not None else hi if hi - t < t - lo else lo
    else:
        at, _ = lines_around(t + px / 2, root, grid)          # the pointer's pixel holds the line drawn on it
    return max(0.0, round(at, 6))


def catch(t: float, grid: Grid, px: float, skip: str = "", extra=()):
    """The kit's Caught for the marker or section edge (or `extra` target: the playhead for a drag) within 6 screen px
    of `t`, strongest first; None when nothing is that near, or not from the screen (`px` 0). `skip`: a marker being
    dragged."""
    targets = [*(grid.marks(skip) if grid.marks else ()), *extra]
    if px <= 0 or not targets:
        return None
    caught = kit_snap.snap(t, targets, 1.0 / px)
    return caught if caught.target is not None else None


def strong_line(t: float, root: dict, reach: float, beats: bool = True) -> float | None:
    """The bar line within `reach` seconds of `t`, else (`beats`) the beat line within it, else None (the grid decides)."""
    b = max(0.0, tempo.beat_at(root, max(0.0, t)))
    s = meter.seg_at(root, b)
    bar0 = s.start + ((b - s.start + EPS) // s.bar) * s.bar
    count = meter.count(s)
    beat0 = bar0 + ((b - bar0 + EPS) // count) * count
    for lo, step in ((bar0, s.bar), (beat0, count))[:2 if beats else 1]:
        near = min((tempo.seconds_at(root, x) for x in (lo, lo + step)), key=lambda x: abs(x - t))
        if abs(near - t) <= reach:
            return near
    return None


def line_name(t: float, root: dict) -> str:
    """What the snap line calls a grid line at `t` seconds: "bar 9" on a bar line, else its place ("9.3", "9.3.2")."""
    pos = musical.position(t, root)
    bar, beat, *rest = pos.split(".")
    return f"bar {bar}" if beat == "1" and not rest else pos


_GRID_NAME = re.compile(r"^(?:bar \d+|\d+(?:\.\d+)+)$")


def snap_words(t: float, root: dict, caught=None, kinds: dict | None = None) -> str:
    """What the snap line's chip calls the place a pointer lands on, before and during the click: a marker
    "Marker: Flash", a section edge "Section: Verse" / "Section: Verse end", the playhead "Playhead", else the grid
    line "Bar 15" / "Beat 15.3" (a finer step: its place, "15.3.2"). `caught`: the kit's Caught (or a name: a drag's
    `snapLine`, its kind then looked up in `kinds`, {name: kind})."""
    name = caught if isinstance(caught, str) else (caught.name if caught is not None else "")
    kind = (kinds or {}).get(name, "") if isinstance(caught, str) else (caught.target.kind if caught is not None and caught.target else "")
    if name and not kind and _GRID_NAME.match(name):
        name = ""                                   # the ruler's own grid words ("bar 9", "9.3"): said as a grid line
    if name:
        if kind == "marker":
            return f"Marker: {name[:1].upper() + name[1:]}"
        if kind == "section":
            return f"Section: {name}"
        return name[:1].upper() + name[1:]          # "Playhead", "Frame 120", a grid line's own words ("bar 9")
    pos = musical.position(t, root)
    bar, beat, *rest = pos.split(".")
    return f"Bar {bar}" if beat == "1" and not rest else f"Beat {bar}.{beat}" if not rest else pos


def frame(t: float, start: float, fps: float) -> tuple[float, int]:
    """(the picture's nearest whole frame to `t` seconds, its number from the picture's first frame at `start`)."""
    n = round((t - start) * fps)
    return max(0.0, round(start + n / fps, 6)), n


write_time = write_like   # `t` seconds in the form `old` was written in (doc/shift.py)


def write_length(old, seconds: float, root: dict, start: float = 0.0):
    """`seconds` long from `start`, in the form `old` was written in."""
    if isinstance(old, dict) and "beats" in old:
        return {"beats": round(tempo.beat_at(root, start + seconds) - tempo.beat_at(root, start), 4)}
    return round(seconds, 4)


midi, name, keys = K.midi, K.pitch_name, K.midis      # pitches: the one place is doc/keys.py


def shift_pitch(p, semis: int):
    """Transpose by `semis`, keeping the form (names stay names, numbers stay numbers, chords stay chords)."""
    if isinstance(p, list):
        return [shift_pitch(x, semis) for x in p]
    k = min(127, max(0, midi(p) + semis))
    return k if isinstance(p, int) else name(k)
