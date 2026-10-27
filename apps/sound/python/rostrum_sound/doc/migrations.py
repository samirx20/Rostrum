"""One small data-only step per change of the .trk file format (rostrum_core DocKind.migrations): step n takes a
document saved as format n to format n+1, run on open before the document is checked. Raising `FORMAT` in kind.py
means adding its step here (the kind refuses to start without it).

    1 → 2   level matching (preset_level.py): the compiler now puts each instrument's measured gain under the track's
            volume, so every existing track's volume (and volume lane) is divided by that gain: the song renders
            exactly as before. The table is part of the format; changing a gain needs a step 2 → 3, never an edit.
    2 → 3   the plain instrument names play recorded instruments and the kits are drums / studio / classic (2026-10-25):
            a drum kit saved as "synth" (the only kit there was) opens as "drums", and each track's volume is moved from
            the old table's gain to the new one (`preset_levels_format2.json` is the old table, frozen), so the song keeps
            its loudness with the new sounds.
    3 → 4   a sensible starting balance (2026-10-25): drum kits, bass and brass sit lower, strings a little higher at the
            same volume (`mix_offsets.json`). Each track's volume is moved from the old table's gain to the new one
            (`preset_levels_format3.json` is the old table, frozen), so a saved song sounds exactly as before.
    4 → 5   gentle limiting (2026-10-25): a new song's master turns the whole mix down rather than limit its loudest
            moment by more than 2 dB (master `gentle`, `maxLimit`). A saved song's master gets `gentle` off: it
            limits as hard as before, so it sounds exactly as before.
    5 → 6   endings and kits (2026-10-25): a new song rings out past its length (`ringOut`) and its drum kits are
            even (track `evenKit`: pieces at measured levels, transients in reach of each hit's loudness). A saved
            song gets both off: it ends and its drums sound exactly as before.
    6 → 7   the recorded bass at its true pitch (2026-10-26): Growlybass names each sample an octave above what it
            sounds, so `bass` (`electricBass`, `bassGuitar`) played every note an octave below the one written. The
            engine now plays it as written; a saved song's notes on those tracks move down an octave (spelling kept),
            so it sounds exactly as before. The names are frozen here: they are what format 6 played low.
    7 → 8   sections on their bars (2026-10-27): a section made from a time range kept its start and end in seconds, so
            a tempo change left it behind its notes (critic r12). Such a time is now kept as the beat it falls on; a
            saved song's plain-seconds section times become those beats (same place today), marker references stay.
"""
from __future__ import annotations

from .. import names
from . import keys, preset_level, tempo

VOLUME_MAX = 4.0        # the fader's top (and the engine's)


def level_matched(data: dict, lists: dict):
    n, capped = 0, 0
    for t in data.get("tracks", []):
        g = preset_level.gain(t, preset_level.FORMAT2)
        if g == 1.0:
            continue
        n += 1
        if "volume" in t:
            was = t["volume"] / g
            t["volume"] = round(min(was, VOLUME_MAX), 6)
            capped += was > VOLUME_MAX
        for lane in t.get("automation", []):
            if lane.get("lane") == "volume":
                lane["points"] = preset_level.scaled(lane["points"], 1 / g, cap=VOLUME_MAX)
    said = f"Level matching: {n} track volume{'s' * (n != 1)} offset so the song sounds as before"
    return data, said + (f" ({capped} held at the fader's top, a little quieter)" if capped else "")


def plain_names(data: dict, lists: dict):
    kits, moved = 0, 0
    for t in data.get("tracks", []):
        old = preset_level.gain(t, preset_level.FORMAT2)
        if t.get("kit") in names.OLD_KITS:         # every track stores its kit (the switch default), whatever its instrument
            t["kit"] = names.OLD_KITS[t["kit"]]
            kits += t.get("instrument") == "kit"
        g = old / preset_level.gain(t, preset_level.FORMAT3)     # what format 3 held; balance() moves it on
        if abs(g - 1) < 1e-6:
            continue
        moved += 1
        if "volume" in t:
            t["volume"] = round(min(t["volume"] * g, VOLUME_MAX), 6)
        for lane in t.get("automation", []):
            if lane.get("lane") == "volume":
                lane["points"] = preset_level.scaled(lane["points"], g, cap=VOLUME_MAX)
    said = f"The drum kit \"synth\" is now \"drums\" on {kits} track{'s' * (kits != 1)}" if kits else ""
    lev = f"{moved} track volume{'s' * (moved != 1)} moved to the new instruments' level matching" if moved else ""
    return data, "; ".join(w for w in (said, lev) if w) or "Instrument names: nothing to change"


def balance(data: dict, lists: dict):
    moved = 0
    for t in data.get("tracks", []):
        g = preset_level.gain(t, preset_level.FORMAT3) / preset_level.gain(t)
        if abs(g - 1) < 1e-6:
            continue
        moved += 1
        if "volume" in t:
            t["volume"] = round(min(t["volume"] * g, VOLUME_MAX), 6)
        for lane in t.get("automation", []):
            if lane.get("lane") == "volume":
                lane["points"] = preset_level.scaled(lane["points"], g, cap=VOLUME_MAX)
    return data, f"{moved} track volume{'s' * (moved != 1)} moved to the new starting balance, so the song sounds as before" if moved else "Starting balance: nothing to change"


def gentle_limiting(data: dict, lists: dict):
    for m in data.get("master", []):
        m.update(gentle=False, maxLimit=2)
    return data, "The master limits as it did (Gentle limiting off), so the song sounds as before"


def endings_and_kits(data: dict, lists: dict):
    data["ringOut"] = False
    for t in data.get("tracks", []):
        t["evenKit"] = False
    return data, "The song ends at its length and its drum kits play as recorded (Ring out and Even kit off), so it sounds as before"


OCTAVE_LOW = ("bass", "electricBass", "bassGuitar")     # the names format 6 played an octave below the written note


def _octave_down(p):
    if keys.midi(p) < 12:
        raise ValueError(f"the note {p!r} on a bass track has no octave below it")
    if isinstance(p, int):
        return p - 12
    m = keys.PITCH.match(p)
    return f"{m.group(1)}{m.group(2) or ''}{int(m.group(3)) - 1}"


def bass_true_pitch(data: dict, lists: dict):
    moved = 0
    for t in data.get("tracks", []):
        if t.get("instrument") != "builtIn" or t.get("builtIn") not in OCTAVE_LOW:
            continue
        for n in t.get("notes", []):
            p = n["pitch"]
            n["pitch"] = [_octave_down(x) for x in p] if isinstance(p, list) else _octave_down(p)
        moved += 1
    return data, (f"The bass now plays at the written pitch: the notes on {moved} bass track{'s' * (moved != 1)} moved down "
                  "an octave, so the song sounds as before") if moved else "Bass pitch: nothing to change"


def sections_on_bars(data: dict, lists: dict):
    moved = 0
    for sec in data.get("sections", []):
        for k in ("at", "end"):
            v = sec.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                sec[k] = {"beat": round(tempo.beat_at(data, float(v)), 6)}
                moved += 1
    return data, ("Sections now stay on their bars when the tempo changes: "
                  f"{moved} section time{'s' * (moved != 1)} kept as beats, in the same place") if moved else "Sections on bars: nothing to change"


# What each step's label starts with or holds, for upgrade steps written before steps carried their formats
# (rostrum_core formats.py; frozen: the labels those builds wrote).
_SAID = {1: ("Level matching:",), 2: ('The drum kit "synth" is now', "moved to the new instruments' level matching",
                                      "Instrument names:"),
         3: ("moved to the new starting balance", "Starting balance:"), 4: ("(Gentle limiting off)",),
         5: ("(Ring out and Even kit off)",), 6: ("The bass now plays at the written pitch", "Bass pitch:"),
         7: ("Sections now stay on their bars", "Sections on bars:")}


def upgraded(label: str):
    """(from, to): the formats an upgrade step with this label took a song between, or None (not a format step)."""
    ran = [n for n, said in _SAID.items() if any(w in label for w in said)]
    return (min(ran), max(ran) + 1) if ran else None


STEPS = {1: level_matched, 2: plain_names, 3: balance, 4: gentle_limiting, 5: endings_and_kits, 6: bass_true_pitch, 7: sections_on_bars}
FORMAT = len(STEPS) + 1
