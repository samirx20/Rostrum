"""Hearing a Library entry through the engine (DESIGN.md §3.2b, §3.7): `render_audition` builds a tiny song and
renders it with the engine's normal render request, the same path as render_mix, so what you audition is what the
song would sound like (one audio engine). Nothing in the person's document changes.

    entry = {"instrument": "builtIn", "builtIn": "piano"}    # an instrument (builtIn / synth / model / sfz / plugin)
          | {"instrument": "kit"}                                # a drum kit (kit / kitSfz)
          | {"media": r"C:\\...\\door.wav", "in": 0.4, "length": 1.2}   # a sound file (or a stretch of one), as itself
    render_audition(engine, entry, doc=doc.data, track="pad")    # -> {"file", "seconds", "cached", "what"}

An instrument plays the track's own notes (`track` given and it has some: the first `bars` bars from `start`), else
a short neutral phrase; either is moved by octaves into the instrument's range (roles.py), so a clarinet or a
flute is heard, never refused for a note it can't play; a kit plays a one-bar pattern. A file is trimmed to MAX_S. The WAV is kept
by content in the engine's share of the one cache (`sound/auditions/`, under the cache cap): the same audition
again is the same file, found at once.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rostrum_core import RostrumError, codes
from rostrum_core.cache import LEVELS, put_file

from . import roles, settings
from .builder import Song
from .compile import compile as compile_doc
from .doc import keys, meter, times

MAX_S = 6.0
BARS = 4
LOW = ("bass", "sub")                       # a bass-like sound is tried an octave range lower
PHRASE = ["C3", "E3", "G3", "C4", "E4", "G4", "C5"]
PHRASE_LOW = ["C1", "E1", "G1", "C2", "E2", "G2", "C3"]
STEP = 0.4
KEY_S = 0.8                                  # a clicked key sounds this long
GM = {"kick": (0, 1.0), "hat": (0.25, 0.5), "snare": (0.5, 0.9)}        # drum -> (beat fraction of a bar, vel)


def _fail(problem: str, subject="audition", hint=None):
    raise RostrumError(codes.BAD_ARGUMENT, "render_audition", subject, problem, (), hint)


def _kind(entry: dict) -> str:
    if "media" in entry:
        return "file"
    inst = entry.get("instrument")
    if inst in ("kit", "kitSfz"):
        return "kit"
    if inst == "voice":
        _fail("a voice needs its model and a line to say; it can't be tried from the Library yet",
              f"voice {entry.get('voice', '')}", "Add the voice track, then listen to it with render_mix.")
    if inst in ("builtIn", "synth", "model", "sfz", "plugin"):
        return "instrument"
    _fail("is not something that can be tried: give an instrument, a drum kit or a sound file",
          json.dumps(entry)[:80])


def entry_of(track: dict) -> dict:
    """The track's own sound as an entry: its instrument and that instrument's one field (a track keeps the fields of
    instruments it played before, e.g. `kit` on a piano track; only the one it plays now is its sound)."""
    inst = track.get("instrument")
    return {"instrument": inst, **({inst: track[inst]} if track.get(inst) is not None else {})}


def _own_notes(doc: dict, track: str, start: float, bars: int) -> list[dict]:
    """The track's notes (and hits) from `start` for `bars` bars, as seconds from 0: [{pitch|drum, at, dur, vel}]."""
    t = next((x for x in doc.get("tracks", []) if x["id"] == track), None)
    if t is None:
        raise RostrumError.not_found("render_audition", "track", track, [x["id"] for x in doc.get("tracks", [])])
    span = bars * meter.start_bar(doc) * 60 / doc.get("tempo", 120)
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


def _in_range(entry: dict, rows: list[dict]) -> list[dict]:
    """The notes moved into the instrument's range (roles.py low / high): the whole phrase by the fewest octaves that
    fit it, else each note on its own. Unchanged for a sound with no range (a synth, an SFZ file)."""
    role = roles.ROLES.get(roles.key(entry) or "")
    if not role or not role.low:
        return rows
    lo, hi = keys.midi(role.low), keys.midi(role.high)
    every = [m for r in rows for m in keys.midis(r["pitch"])]
    shift = next((k for k in (0, 12, -12, 24, -24, 36, -36) if every and lo <= min(every) + k and max(every) + k <= hi), None)

    def fit(m: int) -> int:
        if shift is not None:
            return m + shift
        while m < lo:
            m += 12
        while m > hi and m - 12 >= lo:
            m -= 12
        return m
    return [{**r, "pitch": [fit(m) for m in keys.midis(r["pitch"])] if isinstance(r["pitch"], list) else fit(keys.midi(r["pitch"]))}
            for r in rows]


def _song(entry: dict, kind: str, notes: list[dict], doc: dict | None) -> Song:
    s = Song()
    if doc:
        s.set(tempo=doc.get("tempo", 120), beatsPerBar=doc.get("beatsPerBar", 4), beatUnit=doc.get("beatUnit", 4))
    fields = {k: v for k, v in entry.items() if k not in ("name", "in", "length", "media")}
    if kind == "file":
        media = Path(entry["media"])
        if not media.is_file():
            _fail("is not a file", f'"{media}"')
        t0 = float(entry.get("in") or 0)
        length = min(float(entry.get("length") or MAX_S), MAX_S)
        s.track("a").clip(str(media), at=0, in_=t0 if t0 else None, length=round(length, 4), fadeOut=0.04)
    elif kind == "kit":
        t = s.track("a", **fields)
        bar = meter.start_bar(s.root) * 60 / s.root.get("tempo", 120)
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
        for r in _in_range(fields, rows):
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
    what = {"instrument": "its own notes" if notes else "a short phrase", "kit": "its own hits" if notes else "a one-bar pattern",
            "file": "the sound file"}[kind]
    return {**_render(engine, schedule, entry, out_dir), "what": what}


def _lone(engine, doc: dict, track: str, field: str, item: dict, what: str, out_dir: Path | None) -> dict:
    """`item` alone on a copy of `track` (its own sound settings and effects), rendered once into the cache."""
    t = next((x for x in doc.get("tracks", []) if x["id"] == track), None)
    if t is None:
        raise RostrumError.not_found("audition", "track", track, [x["id"] for x in doc.get("tracks", [])])
    lone = {**t, "notes": [], "hits": [], "clips": [], "automation": [], "mute": False, "solo": False, "output": "master",
            field: [item]}
    root = {**doc, "tracks": [lone], "markers": [], "buses": [], "length": KEY_S + 1.5}
    return {**_render(engine, compile_doc(root, master=False), {}, out_dir), "what": what}


def render_key(engine, doc: dict, track: str, pitch: int, out_dir: Path | None = None) -> dict:
    """One key of `track`'s instrument, as the song would play it (the Editor's keyboard: click a key, hear it).
    Returns {file, seconds, cached, what}."""
    return _lone(engine, doc, track, "notes", {"id": "n_key", "type": "note", "pitch": int(pitch), "at": 0, "dur": KEY_S,
                                              "vel": 0.8}, "one key", out_dir)


def render_hit(engine, doc: dict, track: str, drum, out_dir: Path | None = None) -> dict:
    """One hit of `drum` on `track`'s kit, as the song would play it (a drum row's name: click it, hear it)."""
    return _lone(engine, doc, track, "hits", {"id": "h_key", "type": "hit", "drum": drum, "at": 0, "vel": 0.85},
                 "one drum", out_dir)


def _render(engine, schedule: dict, entry: dict, out_dir: Path | None) -> dict:
    """The schedule rendered once into the content-keyed cache: {file, seconds, cached}."""
    folder = Path(out_dir) if out_dir else settings.cache_dir() / "sound" / "auditions"
    out = folder / f"{_key(schedule, entry)}.wav"
    if out.is_file() and out.with_suffix(LEVELS).is_file():
        return {"file": str(out), "seconds": None, "cached": True}
    r = {}
    put_file(out, lambda tmp: r.update(engine.request("render", schedule=schedule, out=str(tmp), stems=[]) or {}),
             "render_audition", beside=(LEVELS,))
    return {"file": str(out), "seconds": r.get("seconds"), "cached": False}
