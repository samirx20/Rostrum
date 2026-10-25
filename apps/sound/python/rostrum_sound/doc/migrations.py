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
"""
from __future__ import annotations

from .. import names
from . import preset_level

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


STEPS = {1: level_matched, 2: plain_names, 3: balance, 4: gentle_limiting}
FORMAT = len(STEPS) + 1
