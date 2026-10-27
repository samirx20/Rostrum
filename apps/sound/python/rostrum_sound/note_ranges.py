"""Notes a track's recorded sound can't play, found from the written song before any render. The ranges are the
engine's own (`range`: the keys its samples cover), asked once per sound and kept. One check for every reader:
look_music's harmony checks, inspect_diagnose / run_script, and the screen's Problems chip, so an agent and a person
hear of an out-of-range note before the render refuses it (critic r7: "0 problems", then only the render failed)."""
from __future__ import annotations

import json

from .ears import voicing as V
from .ears.written import instrument_spec, written_notes

FIXED = ("builtIn", "sfz")         # the instruments with a fixed range (recorded samples); the rest play any key
_KEPT: dict[str, tuple[int, int] | None] = {}


def sound_of(root: dict, track) -> dict | None:
    """The track's instrument as the `range` request takes it, or None when it plays any key (synths, models)."""
    spec = instrument_spec(root, track)
    if not spec or not set(spec) & set(FIXED):
        return None
    return {k: spec[k] for k in spec if k in FIXED}


def kept(inst: dict) -> tuple[bool, tuple[int, int] | None]:
    """(asked already, its range or None for any key) for a sound, from what was kept: never asks the engine (the
    screen's roll reads this on every draw; roll_range.py asks once, off the window's thread)."""
    key = json.dumps(inst, sort_keys=True)
    return key in _KEPT, _KEPT.get(key)


def ask(engine, inst: dict) -> tuple[int, int] | None:
    """The engine's range for a sound, asked once and kept (raises when the engine says no)."""
    key = json.dumps(inst, sort_keys=True)
    if key not in _KEPT:
        rg = engine.request("range", instrument=inst)
        _KEPT[key] = None if "any key" in str(rg.get("note", "")) else (rg["lowKey"], rg["highKey"])
    return _KEPT[key]


def words(name: str, lo: int, hi: int, bad) -> str:
    """The refusal for notes `bad` (MIDI) outside a sound's range: "Timpani plays C2–C4: A1 is below it"."""
    bad = sorted(set(bad))
    under, over = [m for m in bad if m < lo], [m for m in bad if m > hi]
    said = []
    for ms, side in ((under, "below"), (over, "above")):
        if ms:
            names = [V._name(m) for m in ms[:3]] + ([f"{len(ms) - 3} more"] if len(ms) > 3 else [])
            listed = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
            said.append(f"{listed} {'is' if len(ms) == 1 else 'are'} {side} it")
    return f"{name} plays {V._name(lo)}–{V._name(hi)}: " + "; ".join(said)


def ranges(root: dict, engine, tracks) -> tuple[dict, dict]:
    """({track: (lowest MIDI, highest MIDI)}, {track: why it was not checked}) for `tracks`."""
    found, unchecked = {}, {}
    for t in sorted(tracks):
        inst = sound_of(root, t)
        if inst is None:
            unchecked[t] = "its instrument has no fixed range to ask the engine for"
            continue
        try:
            rng = ask(engine, inst)
        except Exception as e:                       # the engine said no: say so, never pretend the range was fine
            unchecked[t] = f"engine range request failed: {e}"
            continue
        if rng is not None:
            found[t] = rng
    return found, unchecked


def problems(root: dict, engine) -> list[dict]:
    """The diagnose rows: one per track with notes its sound can't play, naming them and the range."""
    notes = written_notes(root)
    rng, _ = ranges(root, engine, {n["track"] for n in notes})
    names = {t["id"]: t.get("name") or t["id"] for t in root.get("tracks", [])}
    out = []
    for t, (lo, hi) in rng.items():
        bad = sorted({m for n in notes if n["track"] == t for m in n["midis"] if not lo <= m <= hi})
        if bad:
            said = ", ".join(V._name(m) for m in bad[:6]) + (f" and {len(bad) - 6} more" if len(bad) > 6 else "")
            out.append({"kind": "out-of-range", "item": t,
                        "message": f'Track "{names.get(t, t)}" has notes its sound can\'t play ({said}): it plays '
                                   f"{V._name(lo)}–{V._name(hi)}, so the song can't be rendered"})
    return out
