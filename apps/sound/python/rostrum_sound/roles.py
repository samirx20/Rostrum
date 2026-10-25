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

from . import names


class Role(NamedTuple):
    parts: tuple[str, ...]
    low: str
    high: str
    sounds: str


PARTS = {"comp": "chords that keep time", "bass": "the low line", "lead": "a tune on top",
         "pad": "held chords under everything", "groove": "drums"}

ROLES: dict[str, Role] = {
    # Recorded instruments (ranges: where the recording is: the pack's own range; a note outside it is stretched and thins).
    "builtIn:piano": Role(("comp", "lead"), "A0", "C8", "a recorded concert grand (Salamander, Yamaha C5)"),
    "builtIn:electricPiano": Role(("comp", "lead"), "A1", "C7", "a recorded Wurlitzer electric piano"),
    "builtIn:organ": Role(("pad", "comp"), "A1", "D7", "a recorded drawbar organ"),
    "builtIn:pipeOrgan": Role(("pad",), "C2", "C#7", "a recorded pipe organ, loud registration"),
    "builtIn:guitar": Role(("comp", "lead"), "F1", "B5", "a recorded classical (nylon) guitar"),
    "builtIn:acousticGuitar": Role(("comp", "lead"), "A1", "G6", "a recorded steel-string archtop guitar"),
    "builtIn:electricGuitar": Role(("comp", "lead"), "B1", "D6", "a recorded clean electric guitar"),
    "builtIn:bass": Role(("bass",), "A1", "G5", "a recorded fingered electric bass"),
    "builtIn:uprightBass": Role(("bass",), "C1", "C4", "a recorded plucked double bass"),
    "builtIn:strings": Role(("pad",), "C1", "D6", "a recorded string section (basses to violins, by pitch), sustained"),
    "builtIn:spiccatoStrings": Role(("comp",), "C1", "D6", "the same string section, short and bouncy"),
    "builtIn:violins": Role(("pad", "lead"), "G3", "D6", "a recorded violin section"),
    "builtIn:violas": Role(("pad",), "C3", "D6", "a recorded viola section"),
    "builtIn:cellos": Role(("pad", "bass"), "C2", "F5", "a recorded cello section"),
    "builtIn:basses": Role(("bass", "pad"), "C1", "C4", "a recorded contrabass"),
    "builtIn:violin": Role(("lead",), "G3", "C7", "a recorded solo violin"),
    "builtIn:cello": Role(("lead", "bass"), "C2", "F5", "a recorded solo cello"),
    "builtIn:harp": Role(("comp", "lead"), "E1", "F7", "a recorded concert harp"),
    "builtIn:brass": Role(("pad", "lead"), "F1", "C6", "a recorded brass section (tuba, trombone, horn, trumpet by pitch)"),
    "builtIn:horn": Role(("pad", "lead"), "A1", "F5", "a recorded French horn"),

    "builtIn:trumpet": Role(("lead",), "E3", "C6", "a recorded trumpet"),
    "builtIn:trombone": Role(("pad", "lead"), "A#1", "F4", "a recorded tenor trombone"),
    "builtIn:tuba": Role(("bass",), "F1", "D4", "a recorded tuba"),
    "builtIn:flute": Role(("lead",), "C4", "C7", "a recorded flute"),
    "builtIn:piccolo": Role(("lead",), "G4", "G6", "a recorded piccolo"),
    "builtIn:oboe": Role(("lead",), "A#3", "F6", "a recorded oboe"),
    "builtIn:clarinet": Role(("lead",), "D3", "F#6", "a recorded clarinet"),
    "builtIn:bassoon": Role(("lead", "bass"), "A#1", "D#5", "a recorded bassoon"),
    "builtIn:saxophone": Role(("lead",), "G#2", "F6", "a recorded tenor saxophone"),
    "builtIn:marimba": Role(("lead", "comp"), "F2", "C#7", "a recorded marimba"),
    "builtIn:vibraphone": Role(("lead", "comp"), "F3", "F6", "a recorded vibraphone"),
    "builtIn:xylophone": Role(("lead",), "G3", "C#7", "a recorded xylophone"),
    "builtIn:glockenspiel": Role(("lead",), "G4", "C#7", "a recorded glockenspiel: bright, keep it quiet"),
    "builtIn:tubularBells": Role(("lead",), "C4", "G5", "recorded tubular bells for single strikes"),
    "builtIn:timpani": Role(("bass", "lead"), "C2", "C4", "recorded timpani"),
    # Analog synth presets and the classic synthesized voices (any key; outside the range they thin out or boom).
    "builtIn:warmPad": Role(("pad",), "C2", "C6", "a warm analog synth pad with a slow start"),
    "builtIn:subBass": Role(("bass",), "E1", "G3", "a round, deep analog synth bass"),
    "builtIn:pluck": Role(("lead", "comp"), "C3", "C6", "a short analog synth pluck"),
    "builtIn:choirPad": Role(("pad",), "C3", "C6", "held 'aah' voices (synthesized)"),
    "builtIn:classic.feltPiano": Role(("comp", "lead"), "C2", "C6", "a soft, close synthesized felt piano"),
    "builtIn:classic.grandPiano": Role(("comp", "lead"), "A0", "C8", "a bright synthesized concert grand"),
    "builtIn:classic.warmPad": Role(("pad",), "C2", "C6", "a warm synthesized pad with a slow start"),
    "builtIn:classic.analogStrings": Role(("pad",), "C2", "C6", "a smooth synthesized string ensemble"),
    "builtIn:classic.spiccatoStrings": Role(("comp",), "G2", "E6", "short, bouncy synthesized strings"),
    "builtIn:classic.choirPad": Role(("pad",), "C3", "C6", "held synthesized 'aah' voices"),
    "builtIn:classic.cinematicBrass": Role(("pad", "lead"), "E2", "C5", "big, filmic synthesized brass swells"),
    "builtIn:classic.subBass": Role(("bass",), "E1", "G3", "a round, deep synthesized bass"),
    "builtIn:classic.glassMarimba": Role(("lead",), "C4", "C7", "a glassy, bright synthesized struck bar"),
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
    "kit:drums": Role(("groove",), "", "", "a recorded rock kit (kick, snare, hats, toms, crash, ride; rim, clap and shaker from the studio kit)"),
    "kit:studio": Role(("groove",), "", "", "a recorded studio kit (rusty close-miked drums, claps, shaker)"),
    "kit:classic": Role(("groove",), "", "", "synthesized drums: kick, snare, clap, hats, cymbal, tom, rim"),
}


def key(instrument: dict) -> str | None:
    """The table key of an instrument record ({"builtIn": "subBass"} -> "builtIn:subBass"; a name that plays the same sound
    as a listed one, "feltPiano", gives "builtIn:piano"); None for SFZ / plug-ins."""
    for form in ("builtIn", "model", "synth", "kit"):
        if isinstance(instrument.get(form), str):
            name = names.BUILT_IN_ALIASES.get(instrument[form], instrument[form]) if form == "builtIn" else instrument[form]
            return f"{form}:{name}"
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
