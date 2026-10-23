"""The song's music map as the Timeline draws it (no Qt): every beat's time (the ruler and grid follow tempo
changes and time signatures), the tempo, time signature and key changes, and the sections (SectionBand.qml). All times in seconds, from the one
tempo map (rostrum_sound.doc.tempo)."""
from __future__ import annotations

from rostrum_sound.doc import keys, meter, tempo

from . import timing


def _sorted(items):
    return sorted(items, key=lambda x: x["t"])


def tempos(root: dict) -> list[dict]:
    """The tempo from each change on: the start first."""
    return [{"t": round(s, 6), "bpm": bpm} for _, bpm, s, *_ in tempo.segments(root)]


def tempo_marks(root: dict) -> list[dict]:
    """The tempo changes as items the screen can select and drag (the start tempo is the document's own); `ramp`
    is +1 / -1 while it glides up / down to the next change, else 0."""
    glide = {round(s[2], 6): (s[3] > s[1]) - (s[3] < s[1]) for s in tempo.segments(root)}
    return _sorted({"id": c["id"], "t": (t := timing.sec(c["at"], root, c["id"])), "bpm": c["bpm"],
                    "ramp": glide.get(round(t, 6), 0)} for c in root.get("tempos", []) if "at" in c and "bpm" in c)


def meter_marks(root: dict) -> list[dict]:
    """The time signature changes as flags ("3/4"; the song's own at the start is the header's)."""
    return _sorted({"id": c["id"], "t": timing.sec(c["at"], root, c["id"]), "per": int(c["beatsPerBar"]),
                    "unit": int(c.get("beatUnit", 4))}
                   for c in root.get("meters", []) if "at" in c and "beatsPerBar" in c)


def key_changes(root: dict) -> list[dict]:
    return _sorted({"id": k["id"], "t": timing.sec(k.get("at", 0), root, k["id"]), "key": k.get("key", "")}
                   for k in root.get("keys", []))


def sections(root: dict) -> list[dict]:
    out = []
    for s in root.get("sections", []):
        t = timing.sec(s["at"], root, s["id"])
        out.append({"id": s["id"], "name": s.get("name", s["id"]), "t": t,
                    "end": max(t, timing.sec(s["end"], root, s["id"]))})
    return _sorted(out)


def grid(root: dict, length: float) -> dict:
    """What song() adds for the ruler, grid, readout and section band."""
    return {"beats": meter.count_seconds(root, length), "bars": meter.bar_seconds(root, length), "tempos": tempos(root),
            "tempoMarks": tempo_marks(root), "meterMarks": meter_marks(root), "keys": key_changes(root),
            "sections": sections(root), "key": keys.key_at(root, 0.0) or ""}
