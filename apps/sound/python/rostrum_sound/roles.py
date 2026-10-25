"""Which part each built-in sound suits, in plain words: the one table agents (inspect_engine, inspect_engine (what: instrument),
inspect_library) and the level-match measurement (devtools/level_match.py) read.

    {"builtIn:subBass": Role(parts=("bass",), low="E1", high="G3", sounds="a round, deep synth bass")}

`parts` are the parts the sound is made for, best first: comp (chords that keep time), bass, lead (a tune on top), pad
(held chords under everything), groove (drums). The first is the one its level is matched on (preset_levels.json), so
tracks written as that part at the same volume sit together roughly; check with look_sound (what: levels). `low` / `high` is where it
sounds like itself (synthesized sounds play any key; outside this they thin out or boom). Sampled (SFZ) packs carry
their own range: inspect_engine (what: instrument) reads it from the file.
"""
from __future__ import annotations

from typing import NamedTuple


class Role(NamedTuple):
    parts: tuple[str, ...]
    low: str
    high: str
    sounds: str


PARTS = {"comp": "chords that keep time", "bass": "the low line", "lead": "a tune on top",
         "pad": "held chords under everything", "groove": "drums"}

ROLES: dict[str, Role] = {
    "builtIn:feltPiano": Role(("comp", "lead"), "C2", "C6", "a soft, close felt piano"),
    "builtIn:grandPiano": Role(("comp", "lead"), "A0", "C8", "a bright concert grand"),
    "builtIn:warmPad": Role(("pad",), "C2", "C6", "a warm synth pad with a slow start"),
    "builtIn:analogStrings": Role(("pad",), "C2", "C6", "a smooth analog string ensemble"),
    "builtIn:spiccatoStrings": Role(("comp",), "G2", "E6", "short, bouncy bowed strings"),
    "builtIn:choirPad": Role(("pad",), "C3", "C6", "held 'aah' voices"),
    "builtIn:cinematicBrass": Role(("pad", "lead"), "E2", "C5", "big, filmic brass swells"),
    "builtIn:subBass": Role(("bass",), "E1", "G3", "a round, deep synth bass"),
    "builtIn:glassMarimba": Role(("lead",), "C4", "C7", "a glassy, bright struck bar"),
    "model:guitar": Role(("comp", "lead"), "E2", "E5", "a plucked steel-string guitar"),
    "model:nylonGuitar": Role(("comp", "lead"), "E2", "E5", "a soft plucked nylon guitar"),
    "model:marimba": Role(("lead", "comp"), "C3", "C7", "a wooden marimba"),
    "model:vibraphone": Role(("lead", "comp"), "F3", "F6", "a metal vibraphone that rings"),
    "model:glockenspiel": Role(("lead",), "G5", "C8", "a tiny, very bright bell bar: keep it quiet"),
    "model:tubularBell": Role(("lead",), "C4", "F5", "a church-like tubular bell for single strikes"),
    "model:violin": Role(("lead",), "G3", "E7", "a bowed solo violin"),
    "synth:saw": Role(("pad", "lead"), "C2", "C6", "a buzzy, full synth wave"),
    "synth:square": Role(("pad", "lead"), "C2", "C6", "a hollow, reedy synth wave"),
    "synth:triangle": Role(("lead",), "C3", "C7", "a soft, flute-like synth wave"),
    "synth:sine": Role(("lead", "bass"), "C1", "C7", "a pure tone: a sub under a bass, or a gentle lead"),
    "kit:synth": Role(("groove",), "", "", "electronic drums: kick, snare, clap, hats, cymbal, tom, rim"),
}


def key(instrument: dict) -> str | None:
    """The table key of an instrument record ({"builtIn": "subBass"} -> "builtIn:subBass"); None for SFZ / plug-ins."""
    for form in ("builtIn", "model", "synth", "kit"):
        if isinstance(instrument.get(form), str):
            return f"{form}:{instrument[form]}"
    return None


def line(k: str) -> str:
    """'subBass: bass (the low line); E1-G3; a round, deep synth bass'."""
    r = ROLES[k]
    parts = ", ".join(f"{p} ({PARTS[p]})" for p in r.parts)
    span = f"; sounds best {r.low}-{r.high}" if r.low else ""
    return f"{k.split(':', 1)[1]}: {parts}{span}; {r.sounds}"


def rows() -> list[dict]:
    """Every built-in sound: {sound, parts, low, high, sounds, line}."""
    return [{"sound": k, "parts": list(r.parts), "low": r.low, "high": r.high, "sounds": r.sounds, "line": line(k)}
            for k, r in ROLES.items()]
