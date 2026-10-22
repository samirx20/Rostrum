"""Hearing a Library entry through the engine (DESIGN.md §3.2b, §3.7): `render_audition` builds a tiny song and
renders it with the engine's normal render request, the same path as render_mix, so what you audition is what the
song would sound like (one audio engine). Nothing in the person's document changes.

    entry = {"instrument": "builtIn", "builtIn": "grandPiano"}    # an instrument (builtIn / synth / model / sfz / plugin)
          | {"instrument": "kit"}                                # a drum kit (kit / kitSfz)
          | {"design": "whoosh", "dur": 0.8}                     # a designed sound, as itself
          | {"media": r"C:\\...\\door.wav", "in": 0.4, "length": 1.2}   # a sound file (or a stretch of one), as itself
    render_audition(engine, entry, doc=doc.data, track="pad")    # -> {"file", "seconds", "cached", "what"}

An instrument plays the track's own notes (`track` given and it has some: the first `bars` bars from `start`), else
a short neutral phrase across its range; a kit plays a one-bar pattern. A file or designed sound is trimmed to
MAX_S. The WAV is kept by content in the engine's share of the one cache (`sound/auditions/`, under the cache cap):
the same audition again is the same file, found at once.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rostrum_core import RostrumError, codes
from rostrum_core.cache import put_file

from . import settings
from .builder import Song
from .compile import compile as compile_doc
from .doc import times

MAX_S = 6.0
BARS = 4
LOW = ("bass", "sub")                       # a bass-like sound is tried an octave range lower
PHRASE = ["C3", "E3", "G3", "C4", "E4", "G4", "C5"]
PHRASE_LOW = ["C1", "E1", "G1", "C2", "E2", "G2", "C3"]
STEP = 0.4
GM = {"kick": (0, 1.0), "hat": (0.25, 0.5), "snare": (0.5, 0.9)}        # drum -> (beat fraction of a bar, vel)


def _fail(problem: str, subject="audition", hint=None):
    raise RostrumError(codes.BAD_ARGUMENT, "render_audition", subject, problem, (), hint)


def _kind(entry: dict) -> str:
    if "media" in entry:
        return "file"
    if "design" in entry:
        return "designed"
    inst = entry.get("instrument")
    if inst in ("kit", "kitSfz"):
        return "kit"
    if inst == "voice":
        _fail("a voice needs its model and a line to say; it can't be tried from the Library yet",
              f"voice {entry.get('voice', '')}", "Add the voice track, then listen to it with render_mix.")
    if inst in ("builtIn", "synth", "model", "sfz", "plugin"):
        return "instrument"
    _fail("is not something that can be tried: give an instrument, a drum kit, a designed sound or a sound file",
          json.dumps(entry)[:80])


def _own_notes(doc: dict, track: str, start: float, bars: int) -> list[dict]:
    """The track's notes (and hits) from `start` for `bars` bars, as seconds from 0: [{pitch|drum, at, dur, vel}]."""
    t = next((x for x in doc.get("tracks", []) if x["id"] == track), None)
    if t is None:
        raise RostrumError.not_found("render_audition", "track", track, [x["id"] for x in doc.get("tracks", [])])
    span = bars * doc.get("beatsPerBar", 4) * 60 / doc.get("tempo", 120)
    out = []
    for kind in ("notes", "hits"):
        for n in t.get(kind, []):
            at = times.seconds(n["at"], doc, f"track {track} › {n['id']}")
            if start <= at < start + span:
                row = {"at": round(at - start, 4), **{k: n[k] for k in ("pitch", "drum", "vel", "pan") if k in n}}
                if kind == "notes":
                    row["dur"] = round(min(times.length_seconds(n["dur"], doc, at, n, f"track {track} › {n['id']}"),
                                           start + span - at), 4)
                out.append(row)
    return sorted(out, key=lambda r: r["at"])


def _song(entry: dict, kind: str, notes: list[dict], doc: dict | None) -> Song:
    s = Song()
    if doc:
        s.set(tempo=doc.get("tempo", 120), beatsPerBar=doc.get("beatsPerBar", 4))
    fields = {k: v for k, v in entry.items() if k not in ("name", "in", "length", "media")}
    if kind == "file":
        media = Path(entry["media"])
        if not media.is_file():
            _fail("is not a file", f'"{media}"')
        t0 = float(entry.get("in") or 0)
        length = min(float(entry.get("length") or MAX_S), MAX_S)
        s.track("a").clip(str(media), at=0, in_=t0 if t0 else None, length=round(length, 4), fadeOut=0.04)
    elif kind == "designed":
        s.track("a").sound(fields.pop("design"), at=0, **fields)
    elif kind == "kit":
        t = s.track("a", **fields)
        bar = s.root.get("beatsPerBar", 4) * 60 / s.root.get("tempo", 120)
        hits = [r for r in notes if "drum" in r] or [
            {"drum": d, "at": round(f * bar, 4), "vel": v} for d, (f, v) in GM.items()] + [
            {"drum": "hat", "at": round(f * bar, 4), "vel": 0.4} for f in (0.125, 0.375, 0.625, 0.875)]
        for h in hits:
            t.hit(**h)
    else:
        t = s.track("a", **fields)
        rows = [r for r in notes if "pitch" in r]
        if not rows:
            pitches = PHRASE_LOW if any(w in json.dumps(entry).lower() for w in LOW) else PHRASE
            rows = [{"pitch": p, "at": round(i * STEP, 4), "dur": STEP * 0.9, "vel": 0.7} for i, p in enumerate(pitches)]
            rows.append({"pitch": pitches[:3], "at": round(len(pitches) * STEP, 4), "dur": 1.2, "vel": 0.6})
        for r in rows:
            t.note(**r)
    return s


def _key(schedule: dict, entry: dict) -> str:
    """Content key: the schedule, plus the file's size and time for a sound file (the same path, changed, is new)."""
    extra = ""
    if "media" in entry:
        st = Path(entry["media"]).stat()
        extra = f"{st.st_size}:{st.st_mtime_ns}"
    return hashlib.sha256((json.dumps(schedule, sort_keys=True, default=str) + extra).encode()).hexdigest()[:24]


def render_audition(engine, entry: dict, doc: dict | None = None, track: str | None = None, start: float = 0.0,
                    bars: int = BARS, out_dir: Path | None = None) -> dict:
    """Render `entry` (see the module doc) and return {file, seconds, cached, what}; raises RostrumError in plain words."""
    kind = _kind(entry)
    notes = _own_notes(doc, track, start, bars) if doc and track and kind in ("instrument", "kit") else []
    schedule = compile_doc(_song(entry, kind, notes, doc).tree(), master=False)
    folder = Path(out_dir) if out_dir else settings.cache_dir() / "sound" / "auditions"
    out = folder / f"{_key(schedule, entry)}.wav"
    what = {"instrument": "its own notes" if notes else "a short phrase", "kit": "its own hits" if notes else "a one-bar pattern",
            "designed": "the designed sound", "file": "the sound file"}[kind]
    if out.is_file():
        return {"file": str(out), "seconds": None, "cached": True, "what": what}
    r = {}
    put_file(out, lambda tmp: r.update(engine.request("render", schedule=schedule, out=str(tmp), stems=[]) or {}),
             "render_audition")
    return {"file": str(out), "seconds": r.get("seconds"), "cached": False, "what": what}
