"""What is written to sound at a moment, and what a stretch holds: measurements of the document, never advice.

    at(doc, t)  -> {"t", "tracks": [{"track", "notes": [{"pitch", "midi", "vel", "from_s", "to_s"}],
                                     "hits": [{"drum", "at_s", "vel"}]}], "chord": "Dm7" | None, "pitches": ["D", "F", "A", "C"]}
    over(doc, a, b) -> [{"track", "notes", "hits", "first_s", "last_s", "low", "high", "vel_mean"}]

Seconds come from `ears.arrangement.read` (the same reading look_arrangement draws, so tempo changes, swing, ties and
markers are the app's own); call inside `markers.project(folder)` when the song has project markers. `at` lists a track
only when it has a note sounding at `t` (from_s <= t < to_s) or a hit within HIT_S of it; `pitches` are the pitch classes
sounding across the pitched tracks (drum kits and muted tracks left out), lowest note first; `chord` names them when they
make a triad, seventh or sus chord (a slash names a bass that is not the root), else None. A hit's `vel` is its velocity
times the track's fader there (what `arrangement.read` stores); a note's is the written velocity. `over` counts what starts
in [a, b): `first_s` / `last_s` are the first and last onsets; `low` / `high` name the lowest and highest note (None for a
drum-only track); `vel_mean` averages notes and hits. Clips and voice lines are not listed.
"""
from __future__ import annotations

from .doc import keys
from .ears import arrangement

HIT_S = 0.06          # a drum hit this close to the moment counts as sounding then
CHORDS = (("", (0, 4, 7)), ("m", (0, 3, 7)), ("7", (0, 4, 7, 10)), ("maj7", (0, 4, 7, 11)), ("m7", (0, 3, 7, 10)),
          ("mMaj7", (0, 3, 7, 11)), ("dim", (0, 3, 6)), ("dim7", (0, 3, 6, 9)), ("m7b5", (0, 3, 6, 10)),
          ("aug", (0, 4, 8)), ("sus4", (0, 5, 7)), ("sus2", (0, 2, 7)), ("7sus4", (0, 5, 7, 10)),
          ("6", (0, 4, 7, 9)), ("m6", (0, 3, 7, 9)), ("add9", (0, 2, 4, 7)), ("madd9", (0, 2, 3, 7)))


def _kits(doc: dict) -> set[str]:
    return {t.get("id") for t in doc.get("tracks", []) if t.get("instrument") in ("kit", "kitSfz")}


def chord_name(midis: list[int], key: str | None = None) -> str | None:
    """The chord the pitches make (lowest first), or None; the bass is tried as the root first."""
    pcs = {m % 12 for m in midis}
    if len(pcs) < 3:
        return None
    bass = min(midis) % 12
    for root in [bass, *sorted(pcs - {bass})]:
        have = {(p - root) % 12 for p in pcs}
        for suffix, shape in CHORDS:
            if have == set(shape):
                return keys.pc_name(root, key) + suffix + (f"/{keys.pc_name(bass, key)}" if root != bass else "")
    return None


def at(doc: dict, t: float) -> dict:
    arr, kits, key = arrangement.read(doc), _kits(doc), None
    key = arr["key"]
    tracks, sounding = [], []
    for tr in arr["tracks"]:
        notes = [{"pitch": keys.pitch_name(m, key), "midi": m, "vel": round(v, 3), "from_s": round(s, 4), "to_s": round(e, 4)}
                 for s, e, m, v, _ in tr["notes"] if s <= t < e]
        hits = [{"drum": d, "at_s": round(s, 4), "vel": round(v, 3)} for s, d, v in tr["hits"] if abs(s - t) <= HIT_S]
        if notes or hits:
            tracks.append({"track": tr["id"], "notes": notes, "hits": hits})
            if tr["id"] not in kits and not tr["mute"]:
                sounding += [n["midi"] for n in notes]
    pcs = []
    for m in sorted(sounding):
        if m % 12 not in pcs:
            pcs.append(m % 12)
    return {"t": t, "tracks": tracks, "chord": chord_name(sounding, key), "pitches": [keys.pc_name(p, key) for p in pcs]}


def over(doc: dict, a: float, b: float) -> list[dict]:
    arr, out = arrangement.read(doc), []
    for tr in arr["tracks"]:
        notes = [n for n in tr["notes"] if a <= n[0] < b]
        hits = [h for h in tr["hits"] if a <= h[0] < b]
        if not notes and not hits:
            continue
        onsets = [n[0] for n in notes] + [h[0] for h in hits]
        vels = [n[3] for n in notes] + [h[2] for h in hits]
        out.append({"track": tr["id"], "notes": len(notes), "hits": len(hits), "first_s": round(min(onsets), 4),
                    "last_s": round(max(onsets), 4),
                    "low": keys.pitch_name(min(n[2] for n in notes), arr["key"]) if notes else None,
                    "high": keys.pitch_name(max(n[2] for n in notes), arr["key"]) if notes else None,
                    "vel_mean": round(sum(vels) / len(vels), 3)})
    return out
