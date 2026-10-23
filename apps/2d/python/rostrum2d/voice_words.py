"""A voice-over's lines as 2D shows them on the Sound row (UX_SPEC 3.28; docs/PLAN.md › Sound in 2D (3)): each spoken
line's words, where it starts and ends in seconds, read from the song RostrumSound already gave us whole
(soundtrack.read), through Sound's own readers (voice_lines, doc.times): never a file path of ours. A line whose
take is not made yet is *pending*: it runs to the next line (or 2 s), says so, and plays silent meanwhile (`playing`:
the song as the screen plays it; export reads the song whole and fails loudly on an unmade take). No Qt.
"""
from __future__ import annotations

FALLBACK = 2.0               # seconds shown for a line that has no take yet


def lines(folder, root: dict) -> list[dict]:
    """[{t, end, text, track}] in time order; [] for a song without voice lines."""
    from rostrum_sound import voice_lines
    from rostrum_sound.doc import markers, times
    found = voice_lines.lines(root)
    if not found:
        return []
    out = []
    with markers.project(folder):
        for track, ln in found:
            t = times.seconds(ln["at"], root, f"line {ln['id']}")
            take = voice_lines.take_of(track, ln)
            out.append({"t": round(t, 3), "end": round(t + take.seconds, 3) if take else None, "text": ln["text"],
                        "track": track.get("name") or track["id"], "pending": take is None})
    out.sort(key=lambda r: r["t"])
    for a, b in zip(out, out[1:] + [None]):
        if a["end"] is None:
            a["end"] = b["t"] if b else a["t"] + FALLBACK
    return out


SOUNDS = ("notes", "hits", "clips", "lines")     # what a track can sound with (rostrum_sound.compile)


def playing(folder, root: dict) -> dict:
    """The song as a *playing* screen reads it (Sound's own rule, clean_clips.without_pending): a voice line whose take
    is not made yet is left out (silent, shown pending by `lines`), a clip whose cleaned take is pending plays its
    original. A song left with no sound lasts until its pending lines end. Never used by export, which fails loudly
    rather than ship the wrong sound."""
    from types import SimpleNamespace
    from rostrum_sound import clean_clips, voice_lines
    data = clean_clips.without_pending(SimpleNamespace(data=root)).data
    unmade = {id(ln) for t, ln in voice_lines.lines(data) if voice_lines.take_of(t, ln) is None}
    if not unmade:
        return data
    ends = [r["end"] for r in lines(folder, data) if r["pending"]]
    data = {**data, "tracks": [{**t, "lines": [ln for ln in t["lines"] if id(ln) not in unmade]} if "lines" in t else t
                               for t in data.get("tracks", [])]}
    if data.get("length") is None and not any(t.get(k) for t in data["tracks"] for k in SOUNDS):
        data["length"] = max(ends)
    return data
