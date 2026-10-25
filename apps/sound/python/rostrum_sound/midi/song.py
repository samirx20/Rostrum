"""A MIDI file's events as a song, in beats: what both the import operation and the script layer build from.

    song = from_events(division, tracks)
      {"tempo": 96, "beatsPerBar": 4, "tempos": [(beat, bpm), …], "beatUnit": 4, "meters": [(beat, beats per bar, beat unit), …], "keys": [(beat, "D minor"), …],
       "markers": [(beat, name), …], "sections": [(name, beat, end beat), …],
       "tracks": [{"name", "builtIn" | "kit", "notes": [{pitch, at, dur, vel}], "hits": [{drum, at, vel}],
                   "lanes": {"sustain" | "dynamics" | "vibrato" | "bend": [[{"beat": b}, value], …]}, "bendRange"?}],
       "skipped": ["…why…"]}

Channel 10 is drums: its notes become hits on the drum kit (GM key -> drum name; keys the kit has no drum for are
listed in `skipped`, never dropped silently). Other channels' notes go on a built-in instrument picked from the
General MIDI program (the plain recorded instrument it plays like; change it after the import). Cue points "<name>" … "<name>/end" are sections; every
other marker is a marker. Times are `{"beat": n}`, lengths `{"beats": n}`, velocities 0 … 1. The pedal (CC 64),
expression (CC 11), mod wheel (CC 1) and pitch wheel become the played track's lanes (controllers.py).
"""
from __future__ import annotations

from ..doc import keys as K
from . import controllers

DRUM_CHANNEL = 9
GM_TO_DRUM = {35: "kick", 36: "kick", 37: "rim", 38: "snare", 40: "snare", 39: "clap", 42: "hat", 44: "pedalHat",
              46: "openHat", 41: "tomLow", 43: "tomLow", 45: "tom", 47: "tom", 48: "tomHigh", 50: "tomHigh", 49: "crash",
              51: "ride", 52: "china", 53: "rideBell", 55: "splash", 57: "crash2", 59: "ride2"}
# A drum name -> its GM key (export): the classic kit's names and the recorded kits' (GM) names.
DRUM_TO_GM = {"kick": 36, "rim": 37, "snare": 38, "clap": 39, "hat": 42, "pedalHat": 44, "openHat": 46,
              "tomLow": 41, "tom": 45, "tomHigh": 48, "crash": 49, "cymbal": 49, "ride": 51, "china": 52,
              "rideBell": 53, "splash": 55, "crash2": 57, "ride2": 59}
# General MIDI programs -> the plain recorded instrument name that plays like it (a program listed here wins over its
# family); the family (program // 8) is the fallback.
PROGRAM = {9: "glockenspiel", 11: "vibraphone", 12: "marimba", 13: "xylophone", 14: "tubularBells", 16: "organ", 19: "pipeOrgan",
           24: "guitar", 25: "acousticGuitar", 26: "electricGuitar", 27: "electricGuitar", 28: "electricGuitar", 32: "uprightBass",
           40: "violin", 41: "violas", 42: "cello", 43: "basses", 44: "spiccatoStrings", 45: "spiccatoStrings", 46: "harp",
           47: "timpani", 56: "trumpet", 57: "trombone", 58: "tuba", 60: "horn", 64: "saxophone", 65: "saxophone",
           66: "saxophone", 67: "saxophone", 68: "oboe", 70: "bassoon", 71: "clarinet", 72: "piccolo", 73: "flute",
           74: "flute", 80: "pluck", 81: "pluck", 88: "warmPad", 89: "warmPad", 91: "choirPad"}
FAMILY = {0: "piano", 1: "marimba", 2: "organ", 3: "guitar", 4: "bass", 5: "strings", 6: "strings", 7: "horn", 8: "saxophone",
          9: "flute", 10: "pluck", 11: "warmPad", 12: "warmPad", 13: "marimba", 14: "marimba", 15: "piano"}


CLASSIC = {"tomLow": "tom", "tomHigh": "tom", "crash": "cymbal", "ride": "cymbal", "china": "cymbal", "rideBell": "cymbal",
           "splash": "cymbal", "crash2": "cymbal", "ride2": "cymbal", "pedalHat": "hat"}     # the classic kit has eight drums


def drum_for(key: int, kit: str | None = None) -> str | None:
    """The drum name of a GM key on a kit (the classic kit's nearest of its eight); None for a key with no drum."""
    name = GM_TO_DRUM.get(key)
    return CLASSIC.get(name, name) if kit == "classic" else name


def instrument_for(program: int) -> str:
    return PROGRAM.get(program) or FAMILY[program // 8]


def _beat(tick, division):
    return {"beat": round(tick / division, 4)}


def _notes(events, division, skipped, where):
    """Pairs note-on with its note-off (first on, first off per channel and key); a note never released ends at the
    track's last event."""
    held, notes, last = {}, [], max((t for t, *_ in events), default=0)
    for tick, kind, data in events:
        if kind == "on":
            held.setdefault(data[:2], []).append((tick, data[2]))
        elif kind == "off" and held.get(data[:2]):
            start, vel = held[data[:2]].pop(0)
            notes.append((start, tick, data[0], data[1], vel))
    for (ch, key), ons in held.items():
        for start, vel in ons:
            notes.append((start, max(last, start + 1), ch, key, vel))
            skipped.append(f"{where}: key {key} at beat {start / division:g} was never released (ends at the track's end)")
    return sorted(notes)


def _track(events, division, n, skipped) -> list[dict]:
    name = next((d for _, k, d in events if k == "name" and d), f"midi {n}")
    program = next((d[1] for _, k, d in events if k == "program" and d[0] != DRUM_CHANNEL), 0)
    tones, drums = [], []
    for start, end, ch, key, vel in _notes(events, division, skipped, name):
        at, v = _beat(start, division), round(vel / 127, 3)
        if ch == DRUM_CHANNEL:
            if key in GM_TO_DRUM:
                drums.append({"drum": drum_for(key), "at": at, "vel": v})
            else:
                skipped.append(f"{name}: drum key {key} at beat {at['beat']:g} has no drum on the kit")
        else:
            tones.append({"pitch": key, "at": at, "dur": {"beats": round((end - start) / division, 4)}, "vel": v})
    out = []
    if tones:
        played = [e for e in events if e[1] in ("cc", "bend") and e[2][0] != DRUM_CHANNEL]
        lanes, bend_range = controllers.to_lanes(played, division)
        out.append({"name": name, "builtIn": instrument_for(program), "notes": tones, "hits": [], "lanes": lanes,
                    **({"bendRange": bend_range} if bend_range is not None else {})})
    if drums:
        out.append({"name": f"{name} drums" if tones else name, "kit": "drums", "notes": [], "hits": drums})
    return out


def from_events(division: int, tracks: list[list]) -> dict:
    song = {"tempo": 120.0, "beatsPerBar": 4, "beatUnit": 4, "tempos": [], "meters": [], "keys": [], "markers": [],
            "sections": [], "tracks": [], "skipped": []}
    cues = {}
    for events in tracks:                       # meta events may sit on any track (format 1: usually the first)
        for tick, kind, data in events:
            b = round(tick / division, 4)
            if kind == "tempo":
                bpm = round(60_000_000 / data, 3)
                if tick == 0:
                    song["tempo"] = bpm
                else:
                    song["tempos"].append((b, bpm))
            elif kind == "timesig":
                if tick == 0:
                    song["beatsPerBar"], song["beatUnit"] = data
                else:
                    song["meters"].append((b, *data))
            elif kind == "key":
                song["keys"].append((b, K.from_signature(*data)))
            elif kind == "marker" and data:
                song["markers"].append((b, data))
            elif kind == "cue" and data:
                if data.endswith("/end") and data[:-4] in cues:
                    song["sections"].append((data[:-4], cues.pop(data[:-4]), b))
                else:
                    cues[data] = b
    song["markers"] += [(b, name) for name, b in cues.items()]      # a cue point with no end is a marker
    for n, events in enumerate(tracks, 1):
        song["tracks"] += _track(events, division, n, song["skipped"])
    for k in ("tempos", "meters", "keys", "markers", "sections"):
        song[k] = sorted(set(song[k]), key=lambda x: x[1] if k == "sections" else x[0])
    return song
