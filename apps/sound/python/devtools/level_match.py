"""Measures every built-in instrument, played instrument, synth wave and kit on one reference phrase and writes the
level-match table (`rostrum_sound/library_data/preset_levels.json`, read by doc/preset_level.py).

    python devtools/level_match.py [--engine <rostrum-sound.exe>] [--check]

Each preset plays the same phrase at the track's own default (volume 1, velocity 0.8) in its home octave, all in one
render; the engine reports each track's integrated loudness (LUFS). The median preset is the reference;
every other gets the gain that brings its phrase to the same loudness, so equal track volumes sound balanced.
`--check` measures again with the table applied and prints the spread instead of writing. The table is part of
the file format: songs already saved hold volumes offset by it (doc/migrations.py), so changing a number needs a new
format step there, never just a new table.
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

from rostrum_sound import names, run_source  # noqa: E402
from rostrum_sound.compile import compile  # noqa: E402
from rostrum_sound.doc import preset_level  # noqa: E402
from rostrum_sound.engine import Engine  # noqa: E402

TABLE = Path(preset_level.__file__).resolve().parents[1] / "library_data" / "preset_levels.json"
PHRASE = "C E G E A C E C F A C A G B D B".split()      # a line, a note a beat: 4 bars at 120 bpm, I – vi – IV – V
CHORDS = [("C", "C E G"), ("A", "A C E"), ("F", "F A C"), ("G", "G B D")]       # the same bars as triads, two a bar
HOME_OCTAVE = {"subBass": 2, "cinematicBrass": 3, "warmPad": 3, "analogStrings": 3, "guitar": 3, "nylonGuitar": 3,
               "saw": 3, "square": 3, "triangle": 3, "sine": 3, "glockenspiel": 5, "glassMarimba": 5}
# How each is played in a song, so what is measured is what it is used for: lines (a bass, a melody, a solo) or
# chords (comping, pads, strings, brass). Written into the table, so the role behind a number is visible.
LINES = ("subBass", "glassMarimba", "marimba", "glockenspiel", "tubularBell", "violin", "sine")


def pitched(form: str, name: str) -> tuple[str, str]:
    octave = HOME_OCTAVE.get(name, 4)
    if name in LINES:
        notes = ", ".join(f"('{p}{octave}', {i}, 1.5)" for i, p in enumerate(PHRASE))
        role = "line"
    else:
        notes = ", ".join(f"('{n}{octave}', {i * 2}, 2)" for i, (_, c) in enumerate(CHORDS * 2) for n in c.split())
        role = "chords"
    return role, (f"s = track('{form}_{name}', {form}='{name}')\n"
                  f"for p, i, d in [{notes}]:\n    s.note(p, at=beat(i), dur=beats(d))\n")


def kit(name: str) -> str:
    lines = [f"d = track('kit_{name}', kit='{name}')\nfor bar_ in range(4):\n    b = bar_ * 4"]
    lines += [f"    d.hit('kick', at=beat(b + {x}))" for x in (0, 2, 2.5)]
    lines += [f"    d.hit('snare', at=beat(b + {x}))" for x in (1, 3)]
    lines += [f"    d.hit('hat', at=beat(b + {x / 2}))" for x in range(8)]
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
