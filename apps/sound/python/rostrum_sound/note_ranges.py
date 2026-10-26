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


def ranges(root: dict, engine, tracks) -> tuple[dict, dict]:
    """({track: (lowest MIDI, highest MIDI)}, {track: why it was not checked}) for `tracks`."""
    found, unchecked = {}, {}
    for t in sorted(tracks):
        spec = instrument_spec(root, t)
        if not spec or not set(spec) & set(FIXED):
            unchecked[t] = "its instrument has no fixed range to ask the engine for"
            continue
        inst = {k: spec[k] for k in spec if k in FIXED}
        key = json.dumps(inst, sort_keys=True)
        try:
            if key not in _KEPT:
                rg = engine.request("range", instrument=inst)
                _KEPT[key] = None if "any key" in str(rg.get("note", "")) else (rg["lowKey"], rg["highKey"])
        except Exception as e:                       # the engine said no: say so, never pretend the range was fine
            unchecked[t] = f"engine range request failed: {e}"
            continue
        if _KEPT[key] is not None:
            found[t] = _KEPT[key]
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
