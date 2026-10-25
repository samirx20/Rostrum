"""The right-click menu of a drum row's name (SPEC § 3.8), as the kit's ActionMenu rows. Data only, no Qt; each value is
"at:drum:<what>:<drum>:…", run by `DrumStepSlots.runDrum`. Rows show only where they apply: Select all and Clear when the
drum has hits, Change drum when there is another drum to change to.

    Hear · Select all <Drum> hits · Fill ▸ (Every step · Every 2nd step · Every beat · Off-beats · Downbeats · Fill row…)
    · Clear · Change drum ▸ (the kit's other drums)

Fill acts on the time range when there is one, else on the bar under the pointer; Clear and Change drum on the time
range's hits of that drum, or on all of them. (A range is "<from>:<to>" seconds; "all" for every hit.)
"""
from __future__ import annotations

from rostrum_sound.doc import tempo

from . import timing

# (label, spacing, where the first hit lands as a share of the spacing): spacings, never grooves.
# A spacing is beats, or "beat" (the time signature's beat there) / "bar" (that bar's length).
SPACINGS = [("Every step", 0.25, 0.0), ("Every 2nd step", 0.5, 0.0), ("Every beat", "beat", 0.0), ("Off-beats", "beat", 0.5),
            ("Downbeats", "bar", 0.0)]


def beats_of(root: dict, every, at_seconds: float) -> float:
    """A spacing in beats at `at_seconds`."""
    if isinstance(every, (int, float)):
        return float(every)
    g = timing.Grid()
    g.value = every
    return g.beats(root, tempo.beat_at(root, at_seconds))


def bar_scope(root: dict, t: float) -> tuple[float, float]:
    """The bar `t` seconds is in, as (start, end) seconds."""
    g = timing.Grid()
    g.value = "bar"
    lo, hi = timing.lines_around(t, root, g)
    return round(lo, 6), round(hi, 6)


def _row(value, label, group, sub=None):
    return {"value": value, "label": label, "keys": "", "group": group, "sub": sub or []}


def entries(root: dict, drum: str, words: str, fill: tuple[float, float], clear, has_hits: bool, others: list) -> list[dict]:
    """The rows of `drum` (`words`: "Hat"): `fill` the (from, to) seconds Fill acts on, `clear` the (from, to) Clear and
    Change drum act on (None: every hit), `has_hits`: the drum has hits there, `others`: [(drum, words)] it could change to."""
    a, b = fill
    where = "all" if clear is None else f"{clear[0]}:{clear[1]}"
    fills = []
    for label, every, share in SPACINGS:
        n = beats_of(root, every, a)
        fills.append(_row(f"at:drum:fill:{drum}:{n:g}:{share * n:g}:{a}:{b}", label, "fill"))
    fills.append(_row(f"at:drum:fillrow:{drum}:{a}:{b}", "Fill row…", "more"))
    out = [_row(f"at:drum:hear:{drum}", "Hear", "hear")]
    if has_hits:
        out.append(_row(f"at:drum:select:{drum}", f"Select all {words.lower()} hits", "hear"))
    out.append(_row(f"at:drum:fills:{drum}", "Fill", "edit", fills))
    if has_hits:
        out.append(_row(f"at:drum:clear:{drum}:{where}", "Clear", "edit"))
        if others:
            out.append(_row(f"at:drum:changes:{drum}", "Change drum", "edit",
                            [_row(f"at:drum:change:{drum}:{d}:{where}", w, "drums") for d, w in others]))
    return out
