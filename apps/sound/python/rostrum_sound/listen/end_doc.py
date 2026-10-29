"""end_doc: how the song's notes end, read from the document (not the audio), for end_check.py.

Round sound-motion: Morning Light ended on IV (unresolved, the judges heard it), and Ascent r3's parts fell silent about
4 s before the end, so the piece thinned to nothing before it ended. Both are written in the notes: the last chord is
the notes sounding at the last onset of the pitched parts (drum kits left out), the final landing is that onset.

    last_chord(data) -> {"at_s", "bass", "pcs", "key", "tonic", "resolved"} | None   (None: no pitched notes or no key)
    dropped(data) -> {"land_s", "parts": [ids], "out": [(id, last end s)]} | None
Times go through doc/times.py: call inside markers.project(folder) when the song has project markers.
"""
from __future__ import annotations

from ..doc import keys as K
from ..doc import times

KITS = ("kit", "kitSfz")
CHORD_S = 0.25        # notes starting this close before the last onset belong to the last chord (a strum, a pickup)
TONIC_TONES = (0, 3, 4, 7)   # over the tonic: the home chord in an inversion still stands on home
SECTION_S = 12.0      # a part that played in this stretch before the landing belongs to the ending
EARLY_S = 2.0         # a part whose last note ends this long before the landing has dropped out


def _notes(data) -> list[tuple[str, float, float, list[int]]]:
    """(track id, start s, end s, midi pitches) of every pitched note, drum kits and muted tracks left out."""
    out = []
    for t in data.get("tracks") or []:
        if t.get("mute") or t.get("instrument") in KITS:
            continue
        for n in t.get("notes") or []:
            try:
                at = times.seconds(n["at"], data, f"{n.get('id')} at")
                end = at + times.length_seconds(n["dur"], data, at, n)
                p = n.get("pitch")
                ps = [K.midi(x) for x in (p if isinstance(p, list) else [p])]
            except Exception:  # noqa: BLE001  a note the document checks refuse is theirs to name
                continue
            out.append((t.get("id", "?"), at, end, ps))
    return out


def last_chord(data) -> dict | None:
    notes = _notes(data)
    if not notes:
        return None
    land = max(at for _, at, _, _ in notes)
    key = K.key_for(data, land)
    home = K.parse(key) if key else None
    if not home:
        return None
    ps = [p for _, at, end, pp in notes if at >= land - CHORD_S or end > land + 1e-3 for p in pp]
    bass, pcs, tonic = min(ps) % 12, sorted({p % 12 for p in ps}), home[0]
    ok = bass == tonic or (tonic in pcs and (bass - tonic) % 12 in TONIC_TONES)
    return {"at_s": land, "bass": K.pc_name(bass, key), "pcs": pcs, "key": key, "tonic": K.pc_name(tonic, key), "resolved": ok}


def dropped(data) -> dict | None:
    notes = _notes(data)
    if not notes:
        return None
    land = max(at for _, at, _, _ in notes)
    last: dict[str, float] = {}
    for tid, at, end, _ in notes:
        if end > land - SECTION_S:
            last[tid] = max(last.get(tid, 0.0), end)
    out = [(tid, e) for tid, e in last.items() if e < land - EARLY_S]
    return {"land_s": land, "parts": list(last), "out": out}
