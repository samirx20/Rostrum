"""Measures every built-in instrument, played instrument, synth wave and kit on a typical part of its role and writes
the level-match table (`rostrum_sound/library_data/preset_levels.json`, read by doc/preset_level.py).

    python devtools/level_match.py [--engine <rostrum-sound.exe>] [--check]

Each preset plays the phrase of its first part in rostrum_sound/roles.py (the phrases: how the six trial sketches of agents wrote a comp, a bass, a lead line, a
pad and a groove: their notes, lengths and velocities) at the track's volume 1, in a home octave, all in one render;
the engine reports each track's integrated loudness (LUFS). The median is the reference; every preset gets the gain
that brings its phrase to it, so equal track volumes sound balanced for parts written like that. `--check` measures
again with the table applied and prints the spread instead of writing. The table is part of the file format: songs
already saved hold volumes offset by it (doc/migrations.py), so changing a number needs a new format step there,
never just a new table.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
import checkout_paths  # noqa: E402

checkout_paths.use_this_checkout()

from rostrum_sound import names, roles, run_source  # noqa: E402
from rostrum_sound.compile import compile  # noqa: E402
from rostrum_sound.doc import preset_level  # noqa: E402
from rostrum_sound.engine import Engine  # noqa: E402

TABLE = Path(preset_level.__file__).resolve().parents[1] / "library_data" / "preset_levels.json"
# Four bars at 120 bpm over Dm – Gm – Bb – A (voiced as 4 notes: root, third, fifth, seventh) in the preset's octave.
BARS = [("D", "F", "A", "C"), ("G", "Bb", "D", "F"), ("Bb", "D", "F", "A"), ("A", "C", "E", "G")]
OCTAVE = {"comp": 3, "pad": 3, "bass": 2, "lead": 4}
LEAD_OCTAVE = {"glockenspiel": 5, "glassMarimba": 5}


def role(name: str) -> str:
    """The part a preset is measured on: the first of its parts in the one role table (rostrum_sound/roles.py)."""
    return next(r.parts[0] for k, r in roles.ROLES.items() if k.split(":", 1)[1] == name)


def part(name: str) -> str:
    """The notes of the preset's role: `s.note(...)` lines, as an agent writes them (vel is what they wrote)."""
    r, o = role(name), OCTAVE[role(name)] + (LEAD_OCTAVE.get(name, 4) - 4 if role(name) == "lead" else 0)
    lines = []
    for b, voicing in enumerate(BARS):
        t = f"bar({b + 1})"
        chord = [f"{n}{o}" for n in voicing]
        if r == "comp":
            lines += [f"s.chord({chord}, at={t}, dur=beats(1.5), vel=0.65)", f"s.chord({chord}, at={t} + beats(2.5), dur=beats(1.25), vel=0.55)"]
        elif r == "pad":
            lines.append(f"s.chord({chord}, at={t}, dur=beats(4), vel=0.5)")
        elif r == "bass":
            lines += [f"s.note('{voicing[0]}{o}', at={t}, dur=beats(1.5), vel=0.85)", f"s.note('{voicing[0]}{o}', at={t} + beats(2.5), dur=beats(1), vel=0.7)"]
        else:
            phrase = [(voicing[2], 0, 1.5), (voicing[1], 1.5, 0.5), (voicing[3], 2, 1.5), (voicing[2], 3.5, 0.5)]
            lines += [f"s.note('{n}{o}', at={t} + beats({a}), dur=beats({d}), vel=0.7)" for n, a, d in phrase]
    return "\n".join(lines)


def pitched(form: str, name: str) -> tuple[str, str]:
    return role(name), f"s = track('{form}_{name}', {form}='{name}')\n{part(name)}\n"


def kit(name: str) -> str:
    lines = [f"d = track('kit_{name}', kit='{name}')"]
    for b in range(4):
        t = f"bar({b + 1})"
        lines += [f"d.hit('kick', at={t}, vel=0.9)", f"d.hit('kick', at={t} + beats(2.5), vel=0.75)",
                  f"d.hit('snare', at={t} + beats(1), vel=0.8)", f"d.hit('snare', at={t} + beats(3), vel=0.85)"]
        lines += [f"d.hit('hat', at={t} + beats({x / 2}), vel=0.5)" for x in range(8)]
    return "\n".join(lines) + "\n"


def phrases() -> dict[str, tuple[str, str]]:
    """{preset key: (role, script)}"""
    out = {f"builtIn:{n}": pitched("builtIn", n) for n in names.BUILT_INS}
    out |= {f"model:{n}": pitched("model", n) for n in names.MODELS}
    out |= {f"synth:{n}": pitched("synth", n) for n in names.WAVES}
    out |= {f"kit:{n}": ("groove", kit(n)) for n in names.KITS}
    return out


def measure(engine: Engine, out: Path, apply_table: bool) -> dict[str, float]:
    """{preset key: LUFS of its reference phrase}, all in one render (the table applied or not)."""
    ph = phrases()
    doc = run_source("tempo(120); length(bar(5))\n" + "\n".join(code for _, code in ph.values()), "level_match.py")
    got = engine.request("render", schedule=compile(doc, matched=apply_table), out=str(out), stems=[])
    heard = {t["id"]: t["lufs"] for t in got["tracks"]}
    return {k: heard[k.replace(":", "_")] for k in ph}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--engine")
    p.add_argument("--check", action="store_true")
    a = p.parse_args()
    engine = Engine(Path(a.engine) if a.engine else None)
    out = Path(os.environ.get("TEMP", ".")) / "level_match.wav"
    try:
        lufs = measure(engine, out, apply_table=a.check)
    finally:
        engine.close()
    if a.check:
        print(json.dumps({k: round(v, 2) for k, v in lufs.items()}, indent=1))
        print(f"spread {max(lufs.values()) - min(lufs.values()):.2f} LU")
        return
    ref = round(statistics.median(lufs.values()), 2)
    roles = {k: role for k, (role, _) in phrases().items()}
    table = {"about": "Gain that brings each preset's reference phrase (devtools/level_match.py) to the median preset's "
                      "loudness: equal track volumes sound balanced. Measured, not tuned by ear.",
             "referenceLufs": ref,
             "presets": {k: {"role": roles[k], "lufs": round(v, 2), "gain": round(10 ** ((ref - v) / 20), 4)}
                         for k, v in sorted(lufs.items())}}
    TABLE.write_text(json.dumps(table, indent=1) + "\n", encoding="utf-8")
    for k, v in table["presets"].items():
        print(f"{k:24} {v['role']:7} {v['lufs']:7.2f} LUFS  gain {v['gain']:.3f}  ({20 * math.log10(v['gain']):+.1f} dB)")


if __name__ == "__main__":
    main()
