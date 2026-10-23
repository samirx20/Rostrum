"""A MIDI file's events as a song, in beats: what both the import operation and the script layer build from.

    song = from_events(division, tracks)
      {"tempo": 96, "beatsPerBar": 4, "tempos": [(beat, bpm), …], "meters": [(beat, beats per bar), …], "keys": [(beat, "D minor"), …],
       "markers": [(beat, name), …], "sections": [(name, beat, end beat), …],
       "tracks": [{"name", "builtIn" | "kit", "notes": [{pitch, at, dur, vel}], "hits": [{drum, at, vel}]}],
       "skipped": ["…why…"]}

Channel 10 is drums: its notes become hits on a synth kit (GM key -> drum name; keys the kit has no drum for are
listed in `skipped`, never dropped silently). Other channels' notes go on a built-in instrument picked from the
General MIDI program family (change it after the import). Cue points "<name>" … "<name>/end" are sections; every
other marker is a marker. Times are `{"beat": n}`, lengths `{"beats": n}`, velocities 0 … 1.
"""
from __future__ import annotations

from ..doc import keys as K

DRUM_CHANNEL = 9
GM_TO_SYNTH = {35: "kick", 36: "kick", 37: "rim", 38: "snare", 40: "snare", 39: "clap", 42: "hat", 44: "hat",
               46: "openHat", 41: "tom", 43: "tom", 45: "tom", 47: "tom", 48: "tom", 50: "tom", 49: "cymbal",
               51: "cymbal", 52: "cymbal", 53: "cymbal", 55: "cymbal", 57: "cymbal", 59: "cymbal"}
# A drum name -> its GM key (export): the synth kit's names and the GM kit's.
DRUM_TO_GM = {"kick": 36, "rim": 37, "snare": 38, "clap": 39, "hat": 42, "pedalHat": 44, "openHat": 46,
              "tomLow": 41, "tom": 45, "tomHigh": 48, "crash": 49, "cymbal": 49, "ride": 51, "china": 52,
              "rideBell": 53, "splash": 55, "crash2": 57, "ride2": 59}
# General MIDI program families (program // 8) -> the nearest built-in instrument.
FAMILY = {0: "grandPiano", 1: "glassMarimba", 2: "feltPiano", 3: "feltPiano", 4: "subBass", 5: "analogStrings",
          6: "analogStrings", 7: "cinematicBrass", 8: "cinematicBrass", 9: "warmPad", 10: "warmPad",
          11: "warmPad", 12: "feltPiano", 13: "glassMarimba", 14: "glassMarimba", 15: "feltPiano"}


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
            if key in GM_TO_SYNTH:
                drums.append({"drum": GM_TO_SYNTH[key], "at": at, "vel": v})
            else:
                skipped.append(f"{name}: drum key {key} at beat {at['beat']:g} has no drum on the synth kit")
        else:
            tones.append({"pitch": key, "at": at, "dur": {"beats": round((end - start) / division, 4)}, "vel": v})
    out = []
    if tones:
        out.append({"name": name, "builtIn": FAMILY[program // 8], "notes": tones, "hits": []})
    if drums:
        out.append({"name": f"{name} drums" if tones else name, "kit": "synth", "notes": [], "hits": drums})
    return out


def from_events(division: int, tracks: list[list]) -> dict:
    song = {"tempo": 120.0, "beatsPerBar": 4, "tempos": [], "meters": [], "keys": [], "markers": [],
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
                    song["beatsPerBar"] = data[0]
                else:
                    song["meters"].append((b, data[0]))
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
