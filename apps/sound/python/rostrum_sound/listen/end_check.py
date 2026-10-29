"""end_check: one fault, `bad_ending`, naming every way the ending fails, each with its number and what passes.

Three rounds added separate ending checks (chopped_end, faded_end, dead_air_end) that agents juggled and that once
contradicted each other (Morning Light: a reverb tail was "faded" and "dead air" at once); their fixes ("a short last
chord", "the length 1–2 s after it", "make the length end with the sound") pulled agents to end early, and the benches
lost most points on endings. So one check reads them all (round sound-endings, DIAGNOSIS.md: thresholds measured on
every judged bench file; levels from end_level.py, under the loudest 3 s, silences counted up to the asked end):

- dies early: under -30 dB for more than 2.5 s before the asked end (Ascent motion r1 3.95 s, r3 4.30 s; fine ≤ 1.8 s)
- dead air: under -50 dB for more than 0.6 s before the asked end (judged 0.70–0.85 s; fine ≤ 0.55 s)
- chopped: the last 0.5 s of the file still within 15 dB of the loudest (Vault: -4 → -30 in 0.5 s), unless the brief
  asks for a hard stop; a loop brief instead must not drop: nothing 30 dB under the loudest in its last 0.5 s but the
  final 0.2 s (Notes motion sat at -62 to -83 there: judged a hole; Notes tighten r1 fell -9 → -27 before its last
  0.2 s and r2 stayed over -9: both judged to loop cleanly; DIAGNOSIS's "within 12 dB of the median" failed r1)
- faded: the delivery faded out sound louder than -20 dB, on every brief (Vault had no ending words), unless a fade is
  asked (the brief, or ending("fade"))
- unresolved / parts out early (end_doc.py, from the notes): only when an ending is asked (a clean or quiet ending in
  the brief, an end marker, or ending(...) in the script); kept conservative: Morning Light's judged "IV" was V–I in F.
A ring dying into the asked end passes it and arc.py's quiet ending (last 2 s 20 LU under the loudest 3 s) both.

    fault(doc, faded, wav, end_s=None) -> [shared fault]   (at most one; `faded`: deliver's {"faded_s", "rang_s", "from_s"})
"""
from __future__ import annotations

from rostrum_core.mcp import faults as shared

from .. import brief
from . import end_doc
from .end_level import DEAD_UNDER_DB, QUIET_UNDER_DB, measure

DEAD_S = 0.6
QUIET_S = 2.5
CHOP_DB = 15.0
LOOP_DB = 30.0
FADE_DB = 20.0
MOST = 0.5             # more than this share of the ending's parts stopped early: the piece thinned to nothing

ENDS = ("end", "ending", "the end", "clean end", "hard end", "final", "final hit", "button")   # marker names: "it ends here"
# the words that ask for a fade, a hard stop, a loop, an open end, or keep a bad_ending: brief.py

RING = ('write ending("ring", at="#end") ("button" for a hit on the end, "fade" only for an asked fade-out): it lands every '
        'part together on the home chord at the asked end and rings it out past it (up to 2 s past the length is fine); '
        'keep the end where the brief puts it, never earlier')
LOOP = ("no ending: the last bar plays through into bar 1 (no ending(...), no fade, no last chord), the length on the "
        "bar line where bar 1 comes back")
CHORD = 'end on the home chord: ending("ring") lands every part on it (chord=... only when the brief asks another)'
PARTS = 'keep the parts playing into the end and land them together: ending("ring", at="#end") does it'


def asked(doc) -> str | None:
    """Why this song must end on purpose: the script's ending(...), the brief's phrase, or the end marker; else None."""
    data = getattr(doc, "data", None) or {}
    if isinstance(data.get("ending"), dict):
        return f"the script writes ending(\"{data['ending'].get('kind', 'ring')}\")"
    for kind in ("clean_ending", "quiet_ending"):
        said = brief.asks(data, kind)
        if said:
            return f'the brief asks for an ending ("{said}")'
    try:
        from ..doc import markers
        with markers.project(getattr(doc, "folder", None)):
            name = next((n for n, _ in markers.all(data) if n.strip().lower() in ENDS), None)
    except Exception:  # noqa: BLE001  a marker that does not resolve is the document checks' business
        name = None
    return f"the song marks its end (marker '{name}')" if name else None


def _fade_ok(data) -> bool:
    return (data.get("ending") or {}).get("kind") == "fade" or bool(brief.asks(data, "fade_ending"))


def _loop(m) -> list[tuple[str, str]]:
    if m["loop_min_db"] > -LOOP_DB:
        return []
    return [(f"the loop drops at its end: in its last 0.5 s it falls to {m['loop_min_db']:.0f} dB under the loudest 3 s "
             f"before the final 0.2 s, a hole before bar 1 comes back; a loop passes when it stays above -{LOOP_DB:g} dB "
             f"there (the final 0.2 s may ramp down)", LOOP)]


def _audio(m, data) -> list[tuple[str, str]]:
    """(what, fix) per way the heard ending fails."""
    if brief.asks(data, "loop"):
        return _loop(m)
    out, end = [], f"the asked end at {m['end_s']:.2f} s"
    if m["quiet_s"] > QUIET_S:
        out.append((f"it dies early: from {m['quiet_from_s']:.2f} s to {end} ({m['quiet_s']:.1f} s) it sits "
                    f"{QUIET_UNDER_DB:g} dB or more under the loudest 3 s; passes at {QUIET_S:g} s or less", RING))
    elif m["dead_s"] > DEAD_S:
        out.append((f"dead air: nothing is heard ({DEAD_UNDER_DB:g} dB under the loudest 3 s) from {m['heard_until_s']:.2f} s "
                    f"to {end}, {m['dead_s']:.2f} s; passes at {DEAD_S:g} s or less", RING))
    if m["last_max_db"] > -CHOP_DB and not brief.asks(data, "hard_stop"):
        out.append((f"chopped: the file stops while still playing (its last 0.5 s reach {m['last_max_db']:.0f} dB under the "
                    f"loudest 3 s and end at {m['last_db']:.0f}); passes when the last 0.5 s stay {CHOP_DB:g} dB or more "
                    f"under it, the ring died away", RING))
    return out


def _fade(m, faded, data) -> list[tuple[str, str]]:
    if not faded or _fade_ok(data):
        return []
    lv = m["level_at"](faded["from_s"]) if m else None
    if lv is not None and lv <= -FADE_DB:
        return []                                   # what the fade took was already quiet
    at = f" at {lv:.0f} dB under the loudest 3 s" if lv is not None else ""
    return [(f"faded: the delivery faded out what still sounded at the length{at} ({faded['rang_s']:.1f} s of ring, over "
             f"the file's last {faded['faded_s']:.1f} s from {faded['from_s']:.2f} s); passes when what it fades is "
             f"{FADE_DB:g} dB or more under the loudest (or the brief asks for a fade: ending(\"fade\"))", RING)]


def _doc(doc, data) -> list[tuple[str, str]]:
    out = []
    try:
        from ..doc import markers
        with markers.project(getattr(doc, "folder", None)):
            own = (data.get("ending") or {}).get("chord") or brief.asks(data, "open_ending") or brief.asks(data, "loop")
            ch = None if own else end_doc.last_chord(data)
            dr = None if _fade_ok(data) or brief.asks(data, "loop") else end_doc.dropped(data)
    except Exception:  # noqa: BLE001  a document the checks refuse is theirs to name
        return out
    if ch and not ch["resolved"]:
        out.append((f"unresolved: the last chord (at {ch['at_s']:.2f} s) stands on {ch['bass']}, not on home ({ch['tonic']}, "
                    f"the key is {ch['key']}); passes when the last chord's lowest note is {ch['tonic']}", CHORD))
    if dr and dr["parts"] and len(dr["out"]) / len(dr["parts"]) > MOST:
        names = ", ".join(f"{t} at {e:.1f} s" for t, e in dr["out"])
        out.append((f"parts drop out early: {len(dr['out'])} of the {len(dr['parts'])} parts of the last section stop "
                    f"more than {end_doc.EARLY_S:g} s before the final landing at {dr['land_s']:.2f} s ({names}); passes "
                    f"when at most half stop early, the rest landing on the last chord", PARTS))
    return out


def fault(doc, faded: dict | None, wav=None, end_s: float | None = None) -> list[dict]:
    data = getattr(doc, "data", None) or {}
    m = measure(wav, end_s) if wav else None
    fade = _fade(m, faded, data)
    heard = [x for x in (_audio(m, data) if m else []) if not (faded and x[0].startswith("chopped"))]   # the delivery's fade: said by _fade
    found = heard + fade
    why = asked(doc)
    if why:
        found += _doc(doc, data)
    if not found:
        return []
    fixes = list(dict.fromkeys(f for _, f in found))
    return [shared.fault("bad_ending", "the ending fails" + (f" ({why})" if why else "") + ": " + "; ".join(w for w, _ in found),
                         "; ".join(fixes), "the end")]
