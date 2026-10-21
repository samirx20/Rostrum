"""What the Timeline shows, as plain data from the document's root (no Qt): one row per track with its notes,
hits and clips as blocks (seconds), the markers, the song's length and grid, and the piano roll of one track.

A track's hue comes from HUES (the one per-track colour list on the screen), by its place in the song.
A clip without a length plays to the end of its file: the file's length is read once (and cached).
"""
from __future__ import annotations

from functools import lru_cache

from rostrum_sound import names

from . import timing

# no blues: blue is the selection (Theme.accent)
HUES = ["#4fb5a5", "#e0a458", "#d27aa8", "#a0c167", "#b48ce0", "#c98c6b", "#d6c86c", "#e07a6b"]
HIT_SECONDS = 0.12          # how long a drum hit's block is drawn
PEAKS = 48                  # waveform points per clip


@lru_cache(maxsize=256)
def media(path: str) -> tuple[float, tuple[float, ...]]:
    """(seconds, peaks 0..1) of an audio file; (0, ()) when it can't be read (the render reports why)."""
    try:
        import numpy as np
        import soundfile as sf
        data, rate = sf.read(path, always_2d=True, dtype="float32")
    except Exception:  # noqa: BLE001  unreadable here; the engine's render names the problem loudly
        return 0.0, ()
    mono = np.abs(data).max(axis=1)
    if not len(mono):
        return 0.0, ()
    chunks = np.array_split(mono, min(PEAKS, len(mono)))
    peaks = np.array([c.max() for c in chunks])
    top = float(peaks.max()) or 1.0
    return len(mono) / rate, tuple(round(float(p / top), 3) for p in peaks)


def clip_span(c: dict, root: dict) -> tuple[float, float, tuple]:
    """(start, seconds, peaks) of a clip, as it plays."""
    total, peaks = media(c["media"])
    dur = timing.length_sec(c["length"], root) if c.get("length") is not None else max(total - c.get("in", 0), 0)
    if total and peaks:
        a, b = c.get("in", 0) / total, min(1.0, (c.get("in", 0) + dur) / total)
        peaks = peaks[int(a * len(peaks)):max(int(a * len(peaks)) + 1, int(b * len(peaks)))]
    return timing.sec(c["at"], root, c["id"]), max(dur, 0.05), peaks


def note_block(n, root):
    ks = timing.keys(n["pitch"])
    label = " ".join(timing.name(k) for k in ks)
    return {"id": n["id"], "type": "note", "t": timing.sec(n["at"], root, n["id"]),
            "dur": timing.length_sec(n["dur"], root), "keys": ks, "label": label, "vel": n.get("vel", 0.8)}


def hit_block(h, root):
    return {"id": h["id"], "type": "hit", "t": timing.sec(h["at"], root, h["id"]), "dur": HIT_SECONDS,
            "drum": str(h["drum"]), "label": str(h["drum"]), "vel": h.get("vel", 0.85)}


def clip_block(c, root):
    t, dur, peaks = clip_span(c, root)
    label = c["media"].replace("\\", "/").rsplit("/", 1)[-1]
    return {"id": c["id"], "type": "clip", "t": t, "dur": dur, "label": label, "peaks": list(peaks)}


def blocks(track: dict, root: dict) -> list[dict]:
    return ([note_block(n, root) for n in track.get("notes", [])]
            + [hit_block(h, root) for h in track.get("hits", [])]
            + [clip_block(c, root) for c in track.get("clips", [])])


def drums_of(track: dict) -> list[str]:
    """The drum rows a track's piano roll shows: the synth kit's order first, then any others as they come."""
    used = {str(h["drum"]) for h in track.get("hits", [])}
    known = [d for d in [*names.SYNTH_DRUMS, *names.GM_DRUMS] if d in used]
    return list(dict.fromkeys(known + sorted(used - set(known))))


def kind_of(track: dict) -> str:
    """What the piano roll draws for a track: "notes", "drums", "audio" (clips) or "empty"."""
    if track.get("instrument") in ("kit", "kitSfz") or track.get("hits"):
        return "drums"
    if track.get("instrument") not in (None, "none") or track.get("notes"):
        return "notes"
    return "audio" if track.get("clips") else "empty"


def rows(root: dict) -> list[dict]:
    """One row per track for the arrangement: name, hue, mute / solo, kind, and its blocks with lanes 0..1 (top to
    bottom: notes by pitch, one per key of a chord; hits by drum row) so a row reads like a small piano roll."""
    out = []
    for i, t in enumerate(root.get("tracks", [])):
        bl = blocks(t, root)
        ks = [k for b in bl if b["type"] == "note" for k in b["keys"]]
        lo, hi = (min(ks), max(ks)) if ks else (60, 60)
        drums = drums_of(t)
        for b in bl:
            if b["type"] == "note":
                b["lanes"] = [0.5 if hi == lo else 1 - (k - lo) / (hi - lo) for k in b["keys"]]
            elif b["type"] == "hit":
                b["lanes"] = [drums.index(b["drum"]) / max(len(drums) - 1, 1)]
        out.append({"id": t["id"], "name": t.get("name") or t["id"], "hue": HUES[i % len(HUES)],
                    "mute": bool(t.get("mute")), "solo": bool(t.get("solo")), "kind": kind_of(t), "blocks": bl})
    return out


def markers(root: dict) -> list[dict]:
    return sorted(({"id": m["id"], "name": m.get("name", m["id"]), "t": timing.sec(m.get("at", 0), root, m["id"])}
                   for m in root.get("markers", [])), key=lambda m: m["t"])


def song(root: dict) -> dict:
    """The grid and length: what the ruler draws. Without a set length: the last sound + 2 s (as the mix)."""
    ends = [b["t"] + b["dur"] for t in root.get("tracks", []) for b in blocks(t, root)]
    ends += [m["t"] for m in markers(root)]
    length = timing.sec(root["length"], root) if root.get("length") is not None else max(ends, default=0) + 2
    return {"length": max(length, 1.0), "spb": timing.spb(root), "beatsPerBar": int(root.get("beatsPerBar", 4)),
            "tempo": float(root.get("tempo", 120))}


def roll(track: dict | None, root: dict, hue: str = HUES[0]) -> dict:
    """The piano roll of one track: its kind, the key range (notes: at least two octaves around what's there)
    or the drum rows, and its blocks."""
    if track is None:
        return {"id": "", "name": "", "kind": "none", "blocks": [], "lo": 48, "hi": 72, "drums": [], "hue": hue}
    bl = blocks(track, root)
    ks = [k for b in bl if b["type"] == "note" for k in b["keys"]] or [60]
    lo, hi = min(ks) - 4, max(ks) + 4
    if hi - lo < 24:
        mid = (lo + hi) // 2
        lo, hi = mid - 12, mid + 12
    return {"id": track["id"], "name": track.get("name") or track["id"], "kind": kind_of(track), "blocks": bl,
            "lo": max(0, lo), "hi": min(127, hi), "drums": drums_of(track), "hue": hue}
