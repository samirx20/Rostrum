"""The song's music map as the Timeline draws it (no Qt): every beat's time (the ruler and grid follow tempo
changes), the tempo and key changes, and the sections (SectionBand.qml). All times in seconds, from the one
tempo map (rostrum_sound.doc.tempo)."""
from __future__ import annotations

from rostrum_sound.doc import keys, tempo

from . import timing


def _sorted(items):
    return sorted(items, key=lambda x: x["t"])


def tempos(root: dict) -> list[dict]:
    """The tempo from each change on: the start first."""
    return [{"t": round(s, 6), "bpm": bpm} for _, bpm, s in tempo.segments(root)]


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
    return {"beats": tempo.beats(root, length), "tempos": tempos(root), "keys": key_changes(root),
            "sections": sections(root), "key": keys.key_at(root, 0.0) or ""}
