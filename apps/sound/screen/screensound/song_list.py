"""The song's timeline as the settings panel lists it while nothing is selected (SongSettings.qml, SongList.qml; no Qt):
tempo, time signature and key changes, the sections and the markers, each a row {id, t, place, value, pick} in time
order, `place` in bars ("Bar 5", "Bar 5.3" off the bar line; "· drop" when a section or marker is there); `pick` is
false for a project marker (shared with the other apps: not an item of this song, so a click only moves the playhead).
The song's own start tempo and time signature are the document's fields (the panel edits them in place), so they are not rows here. `can` says which
"+" is valid at the playhead (rule of individuality: a "+" is absent where it would mean nothing).
"""
from __future__ import annotations

from rostrum_sound.doc import meter, tempo

from . import music_map, song_edit, timeline

NEAR = 1e-3      # seconds: two things this close are at the same place


def place(root: dict, t: float) -> str:
    """Where `t` seconds is, in bars as the ruler counts them: "Bar 5" on a bar line, else "Bar 5.3"."""
    beat = tempo.beat_at(root, t)
    seg, bars = meter.seg_at(root, beat), meter.bar_at(root, beat)
    whole = int(bars + 1e-6)
    count = (bars - whole) * seg.per
    return f"Bar {whole + 1}" if count < 0.05 else f"Bar {whole + 1}.{int(count + 1e-6) + 1}"


def span(root: dict, t: float, end: float) -> str:
    """A section's bars, both counted in: "Bar 1 – 4" (it ends where bar 5 starts), "Bar 1 – 5.3" off the bar line."""
    last = place(root, end)[4:]
    if "." not in last:
        last = str(int(last) - 1)
    first = place(root, t)
    return first if last == first[4:] else f"{first} – {last}"


def _where(root: dict, t: float, named_places: list[dict]) -> str:
    named = next((s["name"] for s in named_places if abs(s["t"] - t) < NEAR), "")
    return place(root, t) + (f" · {named}" if named else "")


def _bpm(v: float) -> str:
    return f"{v:g} bpm" if v == round(v, 2) else f"{v:.2f} bpm"


def rows(root: dict) -> dict:
    """{tempo, meter, key, sections, markers}: each a list of rows in time order."""
    secs, marks = music_map.sections(root), timeline.markers(root)

    def row(c, value):
        return {"id": c["id"], "t": c["t"], "place": _where(root, c["t"], secs + marks), "value": value, "pick": True}
    glide = {1: " ↗", -1: " ↘", 0: ""}
    return {"tempo": [row(c, _bpm(c["bpm"]) + glide[c["ramp"]]) for c in music_map.tempo_marks(root)],
            "meter": [row(c, f"{c['per']}/{c['unit']}") for c in music_map.meter_marks(root)],
            "key": [row(k, k["key"] or song_edit.NO_KEY) for k in music_map.key_changes(root)],
            "sections": [{"id": s["id"], "t": s["t"], "place": s["name"], "value": span(root, s["t"], s["end"]),
                          "pick": True} for s in secs],
            "markers": [{"id": m["id"], "t": m["t"], "place": m["name"], "pick": not m["shared"],
                         "value": place(root, m["t"]) + (" · shared" if m["shared"] else "")} for m in marks]}


def can(root: dict, t: float) -> dict:
    """Which "+" the panel shows at playhead `t`: a tempo or time signature change only past the start (the start is
    the song's own) and where none is yet (on the beat it would be written on); a marker where none is. (A key
    change: song_edit.state, keyAtPlayhead.)"""
    beat = song_edit.snapped_beat(root, t)
    at_beat = {round(tempo.beat_at(root, c["t"]), 4) for c in music_map.tempo_marks(root)}
    meters = {round(tempo.beat_at(root, c["t"]), 4) for c in music_map.meter_marks(root)}
    return {"tempo": beat > 1e-9 and round(beat, 4) not in at_beat,
            "meter": beat > 1e-9 and round(beat, 4) not in meters,
            "marker": all(abs(m["t"] - t) >= NEAR for m in timeline.markers(root))}
