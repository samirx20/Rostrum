"""Measures every built-in instrument, played instrument, synth wave and kit on a typical part of its role and writes
the level-match table (`rostrum_sound/library_data/preset_levels.json`, read by doc/preset_level.py).

    python devtools/level_match.py [--engine <rostrum-sound.exe>] [--check]

Each preset plays three typical phrases at the track's volume 1, in a home octave, one render per phrase: the phrase of
its first part in rostrum_sound/roles.py (how the six trial sketches of agents wrote a comp, a bass, a lead line, a pad
and a groove: their notes, lengths and velocities), the same notes at the Editor's default velocity (a person drawing
them), and a held line of one note a bar (2026-10-27, critic r12: velocity curves differ a lot between recorded
instruments, so one velocity left the double basses 14 LU under a clarinet). The engine reports each track's
integrated loudness (LUFS); a preset's loudness is the mean of its three. The median is the reference; every preset
gets the gain that brings it there, so equal track volumes start roughly balanced however the part is written. `--check` measures
again with the table applied and prints the spread instead of writing. The table is part of the file format: songs
already saved hold volumes offset by it (doc/migrations.py), so changing a number needs a new format step there,
never just a new table.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
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
LEAD_OCTAVE = {"glockenspiel": 5, "piccolo": 5, "classic.glassMarimba": 5}


def role(name: str) -> str:
    """The part a preset is measured on: the first of its parts in the one role table (rostrum_sound/roles.py)."""
    return next(r.parts[0] for k, r in roles.ROLES.items() if k.split(":", 1)[1] == name)


def part(name: str, shift: int | None = None) -> str:
    """The notes of the preset's role: `s.note(...)` lines, as an agent writes them (vel is what they wrote)."""
    r, o = role(name), OCTAVE[role(name)] + (LEAD_OCTAVE.get(name, 4) - 4 if role(name) == "lead" else 0)
    o += shift or 0
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


def midi(note: str) -> int:
    return 12 * (int(note[-1]) + 1) + {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[note[0]] + ("#" in note) - ("b" in note[1:2])


def fitted(name: str) -> str:
    """The part, moved by whole octaves (nearest first) until every note lies inside the instrument's recorded range."""
    r = roles.ROLES[next(k for k in roles.ROLES if k.split(":", 1)[1] == name)]
    if not r.low:
        return part(name)
    for shift in (0, 1, -1, 2, -2):
        text = part(name, shift)
        notes = [midi(n) for n in re.findall(r"[A-G][b#]?\d", text)]
        if midi(r.low) <= min(notes) and max(notes) <= midi(r.high):
            return text
    raise SystemExit(f"{name}: no octave puts the reference part inside {r.low}-{r.high}")


def pitched(form: str, name: str) -> tuple[str, str]:
    return role(name), f"s = track('{form}_{name.replace('.', '_')}', {form}='{name}')\n{fitted(name)}\n"


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
    out = {f"builtIn:{n}": pitched("builtIn", n) for g in names.BUILT_IN_GROUPS.values() for n in g}   # a name that plays the same sound as a listed one shares its gain
    out |= {f"model:{n}": pitched("model", n) for n in names.MODELS}
    out |= {f"synth:{n}": pitched("synth", n) for n in names.WAVES}
    out |= {f"kit:{n}": ("groove", kit(n)) for n in names.KITS}
    return out


# The Editor's default velocities (a person drawing notes and hits; doc/ops_thin.py DEFAULT_VEL).
HAND = {"note": 0.8, "hit": 0.85}


def by_hand(code: str) -> str:
    """The same part at the Editor's default velocity."""
    code = re.sub(r"(\.(?:note|chord)\(.*?vel=)[0-9.]+", lambda m: m.group(1) + str(HAND["note"]), code)
    return re.sub(r"(\.hit\(.*?vel=)[0-9.]+", lambda m: m.group(1) + str(HAND["hit"]), code)


def held_line(key: str, code: str) -> str:
    """One held note a bar (the chord's root, inside the instrument's range) at the Editor's velocity: a line drawn by
    hand, the way low strings hold a part under a cue (critic r12: double basses on a held D measured -31 LUFS). A kit
    plays its groove by hand."""
    if key.startswith("kit:"):
        return by_hand(code)
    head, *body = code.splitlines()
    o = int(re.findall(r"[A-G][b#]?(\d)", "\n".join(body))[0])
    r = roles.ROLES.get(key)
    lo, hi = (midi(r.low), midi(r.high)) if r and r.low else (0, 127)
    while min(midi(f"{v[0]}{o}") for v in BARS) < lo and o < 8:
        o += 1
    while max(midi(f"{v[0]}{o}") for v in BARS) > hi and o > 0:
        o -= 1
    return "\n".join([head] + [f"s.note('{v[0]}{o}', at=bar({b + 1}), dur=beats(4), vel={HAND['note']})"
                               for b, v in enumerate(BARS)]) + "\n"


PHRASES = {"agent": lambda k, c: c, "hand": lambda k, c: by_hand(c), "line": held_line}


def measure_each(engine: Engine, out: Path, apply_table: bool) -> dict[str, dict[str, float]]:
    """{phrase ("agent" / "hand" / "line"): {preset key: LUFS}}, one render per phrase (the table applied or not)."""
    ph = phrases()
    got = {}
    for name, make in PHRASES.items():
        code = "\n".join(make(k, c) for k, (_, c) in ph.items())
        doc = run_source("tempo(120); length(bar(5))\n" + code, "level_match.py")
        r = engine.request("render", schedule=compile(doc, matched=apply_table), out=str(out), stems=[])
        heard = {t["id"]: t["lufs"] for t in r["tracks"]}
        got[name] = {k: heard[k.replace(":", "_").replace(".", "_")] for k in ph}
    return got


def measure(engine: Engine, out: Path, apply_table: bool) -> dict[str, float]:
    """{preset key: LUFS}: the mean (in dB) of its three typical phrases, the role's part as agents write it, the same
    notes at the Editor's velocity, and a held line, so a plain track starts balanced however it is written."""
    each = measure_each(engine, out, apply_table)
    return {k: statistics.fmean(each[p][k] for p in PHRASES) for k in each["agent"]}


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
    offsets = json.loads(preset_level.OFFSETS.read_text(encoding="utf-8"))["offsetsDb"]     # the starting balance, on top
    table = {"about": "Gain that brings each preset's reference phrase (devtools/level_match.py) to the median preset's "
                      "loudness: equal track volumes sound balanced. Measured, then moved by mix_offsets.json (mixDb) to a sensible starting balance.",
             "referenceLufs": ref,
             "presets": {k: {"role": roles[k], "lufs": round(v, 2), "gain": round(10 ** ((ref - v + offsets.get(k, 0)) / 20), 4),
                                **({"mixDb": offsets[k]} if k in offsets else {})}
                         for k, v in sorted(lufs.items())}}
    TABLE.write_text(json.dumps(table, indent=1) + "\n", encoding="utf-8")
    for k, v in table["presets"].items():
        print(f"{k:24} {v['role']:7} {v['lufs']:7.2f} LUFS  gain {v['gain']:.3f}  ({20 * math.log10(v['gain']):+.1f} dB)")


if __name__ == "__main__":
    main()
