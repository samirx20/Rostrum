"""static_part: a part that plays one sound at one level for many bars in a piece that asks to build.

Round sound-ascent: the judges heard every Rostrum part "hold one sound at one level the whole piece" while the rival's
timbres kept moving. A listening check cannot tell which part that is in a full mix, but the document says it: a track
whose notes, over more than BARS bars or SECONDS of continuous playing (gaps under a bar), keep the same sound and articulation,
an asked level (velocity x lanes x the note's own dynamics, part_read.py) within LEVEL_BAND of the stretch's middle,
and no brightness envelope on its effects. A warning, not a fault (a held pedal or an ostinato can be right), and only
when the brief asks for a build (big_build, quiet_start) or the song marks a climax: there a part that never moves
works against the build.

    stretches(track, data) -> [{"from_s", "to_s", "bars", "level", "art"}] (each longer than BARS bars or SECONDS)
    warnings(doc) -> ["static part: ..."] in plain words
"""
from __future__ import annotations

from .. import brief
from . import arc, squash  # noqa: F401  register quiet_start / big_build
from .core import num
from .part_read import bright_moves, played, sound

BARS = 16            # longer than this many bars of one sound at one level
SECONDS = 24.0       # ...or this long, whichever comes first (Ascent at 66 bpm is under 14 bars long)
LEVEL_BAND = 0.10    # levels within ±10 % of the stretch's middle count as one level


def _asks_build(data) -> str | None:
    from ..doc import markers
    from .weakest import kind_of
    said = brief.asks(data, "big_build") or brief.asks(data, "quiet_start")
    if said:
        return f"the brief asks for \"{said}\""
    name = next((n for n, _ in markers.all(data) if kind_of(n) == "climax"), None)
    return f"the song marks a climax ('{name}')" if name else None


def _bar_len(data, t) -> float:
    """One bar's length in seconds from `t`."""
    from ..doc import meter, tempo
    beat = tempo.beat_at(data, t)
    return tempo.seconds_at(data, beat + meter.seg_at(data, beat).bar) - t


def _bars(data, a, b) -> float:
    from ..doc import meter, tempo
    return meter.bar_at(data, tempo.beat_at(data, b)) - meter.bar_at(data, tempo.beat_at(data, a))


def _steady(levels) -> bool:
    mid = (max(levels) + min(levels)) / 2
    return mid > 0 and (max(levels) - mid) / mid <= LEVEL_BAND


def stretches(track, data) -> list[dict]:
    """The longest steady stretches (same articulation, level within the band, no gap of a bar or more)."""
    notes = played(track, data)
    out, i = [], 0
    while i < len(notes):
        j, levels, end = i, [notes[i]["level"]], notes[i]["end"]
        while j + 1 < len(notes):
            n = notes[j + 1]
            if n["art"] != notes[i]["art"] or n["at"] - end >= _bar_len(data, end) or not _steady(levels + [n["level"]]):
                break
            j, levels, end = j + 1, levels + [n["level"]], max(end, n["end"])
        a = notes[i]["at"]
        bars = _bars(data, a, end)
        if bars > BARS or end - a > SECONDS:
            out.append({"from_s": num(a, 2), "to_s": num(end, 2), "bars": num(bars, 1),
                        "level": num(sum(levels) / len(levels), 2), "art": notes[i]["art"]})
        i = j + 1
    return out


def _bar_no(data, t) -> int:
    from ..doc import meter, tempo
    return int(meter.bar_at(data, tempo.beat_at(data, t))) + 1


def warnings(doc) -> list[str]:
    """One line per steady stretch, in a piece that asks to build (none otherwise)."""
    from ..doc import markers
    data = getattr(doc, "data", None) or {}
    with markers.project(getattr(doc, "folder", None)):
        why = _asks_build(data)
        if not why:
            return []
        out = []
        for t in data.get("tracks") or []:
            if t.get("mute") or bright_moves(t) or not sound(t):
                continue
            for s in stretches(t, data):
                art = f", articulation {s['art']}" if s["art"] else ""
                out.append(
                    f"static part: {t['id']} plays {sound(t)}{art} at one level (about {s['level']:g}, within "
                    f"±{LEVEL_BAND * 100:.0f} %) and one brightness for {s['bars']:g} bars, bars {_bar_no(data, s['from_s'])}–"
                    f"{_bar_no(data, s['to_s'] - 0.01)} ({s['from_s']:g}–{s['to_s']:g} s), and {why}; shape it "
                    f"(t.shape(\"vol\", ...), t.shape(\"bright\", ...), t.shape(\"art\", ...) across those bars), double it with "
                    f"another instrument for the last stretch, or hand the line to another instrument part-way")
        return out
