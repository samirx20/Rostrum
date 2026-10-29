"""A song's ending in one call: `ending(kind, at="#end", chord=None, parts=None, ring=None)`.

    ending("ring", at="#end")              # every part lands together on the home chord at #end and holds it `ring` s
                                           #   (default 2 bars, kept to 3 … 5 s), then lets go; the length ends TAIL_S
                                           #   after that, so the release and the reverb die away inside the file
    ending("button", at=bar(33))           # a short accented chord on bar 33 (+ a kick and a crash on the drum tracks
                                           #   that play there); the length TAIL_S after it (CRASH_TAIL_S with a crash)
    ending("fade", at="#end", ring=8.0)    # the parts keep playing; the master's volume falls to -30 dB over the
                                           #   `ring` s (default 4 bars) before `at`, where the song ends

`at`: a marker, bar(n) or seconds; the default "#end" without such a marker is the last bar line at or before the
length. `chord`: the home chord of key(...) unless a numeral ("V"), symbol ("Gsus4") or pitches (["D3", "F3", "A3"])
is given (script_ending_chord.py). `parts`: the tracks that land (default: every pitched track with notes in the 2 bars
before `at`; for a button also the drum tracks with hits there). Applied when the script ends, after every note is
written: notes ringing across `at` end on it, notes and hits after it are dropped, nothing else is changed. The kinds
make each ending land; which ending fits the piece is the writer's. The length is set only when the script has none:
a length set before stays, and the reply gives the arithmetic against it. A loop has no ending: its last bar plays into bar 1. `song.root["ending"]` keeps what was asked.
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes

from . import script_ending_chord as C
from . import script_moment_edit as E
from .builder import Track
from .doc import keys as K
from .doc import markers, meter, tempo, times
from .script_scope import say
from .script_time import Beat

API = ['ending(kind="ring" | "button" | "fade", at="#end", chord=None, parts=None, ring=None)']
KINDS = ("ring", "button", "fade")
FORMS = ['ending("ring", at="#end")', 'ending("button", at=bar(33))', 'ending("fade", at="#end", ring=8.0)']
TAIL_S = 1.0                  # s from the last let-go to the length: measured 0.6-0.9 s to -60 dBFS (piano, strings, a
CRASH_TAIL_S = 2.0            #   synth pad, with or without a hall); a sampled crash rings 1.8 s (decay= does not shorten it)
RING_ROOM_S = 2.0             # a ring may end this far past an asked length without a word (the usual delivery allowance)
FADE_FLOOR_DB = -30.0         # the fade's floor at `at`; Ring out lets the rest die away (-40 left 0.55 s unheard)


def _refuse(what, why, accepted=FORMS, hint=None):
    raise RostrumError(codes.BAD_ARGUMENT, "ending", what, why, accepted, hint)


def ending(song, kind, at="#end", chord=None, parts=None, ring=None):
    if getattr(song, "ending", None) is not None:
        _refuse("ending(...)", "is written twice: a song has one ending")
    if kind not in KINDS:
        _refuse(f"kind={kind!r}", "is not an ending", [repr(k) for k in KINDS])
    if ring is not None and (isinstance(ring, bool) or not isinstance(ring, (int, float)) or ring <= 0):
        _refuse(f"ring={ring!r}", "is not a number of seconds > 0")
    if kind == "fade" and chord is not None:
        _refuse("chord=", "is not for a fade: the parts keep playing what they play", hint='A last chord: ending("ring").')
    if parts is not None and (not isinstance(parts, (list, tuple)) or not parts or not all(isinstance(t, Track) for t in parts)):
        _refuse(f"parts={parts!r}", "is not a list of tracks (the variables track(...) gave)", ["parts=[piano, strings]"])
    if times.problem(at):
        _refuse(f"at={at!r}", times.problem(at), ['at="#end"', "at=bar(33)", "at=62.0"])
    song.ending = dict(kind=kind, at=at, chord=chord, parts=None if parts is None else list(parts), ring=ring)


def _at(song, root, at):
    """(the time as written, its seconds): "#end" without a marker is the last bar line at or before the length."""
    if at == "#end" and "end" not in markers.by_name(root):
        if song.root.get("length") is None:
            _refuse('at="#end"', "is not there: the song has no marker \"end\" and no length to end at",
                    ['marker("end", at=bar(33)) then ending("ring")', 'ending("ring", at=bar(33))'])
        length = times.seconds(song.root["length"], root, "ending")
        n = int(meter.bars_long(root, length) + 1e-6) + 1
        at = Beat(meter.bar_start(root, n))
    try:
        return at, times.seconds(at, root, "ending")
    except RostrumError as e:
        _refuse(f"at={at!r}", f"does not resolve to a time: {e}", ['at="#end" (a marker the script or song has)', "at=bar(33)", "at=62.0"])


def _pitched(t):
    return t.fields.get("instrument") not in ("kit", "none")


def _recent(song, root, t, start, at_s):
    """The track's notes sounding in [start, at): [(start s, MIDI list, vel)], by start."""
    out = []
    for _, f, _ in t.notes:
        s, e = E._span(t, f, root, "ending")
        if s < at_s - E.AT_ONCE and e > start:
            out.append((s, sorted(K.midis(f["pitch"])), f.get("vel") or 0.8))
    return sorted(out)


def _clear(t, root, at_s, keep_on, counts):
    """Notes across `at` end on it; notes (and hits, unless `keep_on` and on `at`) starting at or after it go."""
    E.edit(t, root, "ending", lambda s: s < at_s - E.AT_ONCE, lambda s, e: at_s if e > at_s else None, counts)
    E.drop_hits(t, root, "ending", lambda s: s < at_s - E.AT_ONCE or (keep_on and s <= at_s + E.AT_ONCE), counts)


def apply(song) -> None:
    asked = getattr(song, "ending", None)
    if asked is None:
        return
    kind, root = asked["kind"], {**song.root, "markers": song.marks()}
    at, at_s = _at(song, root, asked["at"])
    b = tempo.beat_at(root, at_s)
    bar_s = at_s - tempo.seconds_at(root, b - meter.seg_at(root, b).bar)
    window = tempo.seconds_at(root, b - 2 * meter.seg_at(root, b).bar)
    key = K.key_for(root, at_s)
    chosen = asked["parts"] or [t for t in song.tracks if (t.notes if _pitched(t) else kind == "button" and t.hits)
                                and (_recent(song, root, t, window, at_s) if _pitched(t) else
                                     any(window <= times.seconds(h[1]["at"], root, "ending") <= at_s + E.AT_ONCE for h in t.hits))]
    if kind != "fade" and not any(_pitched(t) for t in chosen):
        _refuse(f"at={asked['at']!r}", "has no pitched part playing in the 2 bars before it to land the chord",
                ["parts=[piano, strings]"], "Name the parts that end, or end where they play.")
    counts = E.Counts()
    for t in song.tracks:
        _clear(t, root, at_s, keep_on=kind == "ring", counts=counts)
    said = [counts.said()]
    if kind == "fade":
        span = asked["ring"] or 4 * bar_s
        _fade(song, root, max(0.0, at_s - span), at_s)
        length, said = at_s, said + [f"master fades to {FADE_FLOOR_DB:g} dB over {min(span, at_s):.1f} s before it"]
    else:
        hold = asked["ring"] or min(5.0, max(3.0, 2 * bar_s))
        dur = hold if kind == "ring" else min(0.35, 0.5 * bar_s / meter.seg_at(root, b).per)
        said.append(_land(song, root, chosen, asked["chord"], key, at, at_s, window, dur, kind))
        crash = any(not _pitched(t) for t in chosen)           # a crash struck on `at` rings longer
        length = at_s + dur + (asked["ring"] if kind == "button" and asked["ring"] else CRASH_TAIL_S if crash else TAIL_S)
    old = song.root.get("length")
    old_s = None if old is None else times.seconds(old, root, "ending")
    if old is None:                    # a length the script set is the writer's: never moved (Sam, 2026-10-29)
        song.set(length=round(length, 3), ringOut=True)
    else:
        song.set(ringOut=True)
    song.root["ending"] = {"kind": kind, "at": asked["at"], "at_s": round(at_s, 3), **({"home": key} if key else {}),
                         **({"chord": asked["chord"]} if asked["chord"] is not None else {})}
    sound = (f"fades from {at_s - min(span, at_s):.2f} s to {at_s:.2f} s" if kind == "fade" else
             f"lands {at_s:.2f} s, {'held' if kind == 'ring' else 'struck'} to {at_s + dur:.2f} s, rings to about {length:.2f} s")
    file = f"file {length:.2f} s" if old is None else f"the length stays {old_s:.2f} s as set"
    say(f"ending {kind}: {sound}, {file} (Ring out on). " + "; ".join(said) + "." + _against(old_s, length, at_s))


def _against(asked, length, at_s) -> str:
    """The arithmetic against a length the script set before: past it by more than RING_ROOM_S, or short of it by more
    than a second, says where to land so the ring dies by it (agents pulled `at` early and left a 1.25 s ring)."""
    if asked is None or -1.0 <= length - asked <= RING_ROOM_S:
        return ""
    land = asked - (length - at_s)
    return (f" The length set before was {asked:.2f} s: this ending {'runs' if length > asked else 'stops'} "
            f"{abs(length - asked):.2f} s {'past' if length > asked else 'short of'} it. To end there, put `at` at about {land:.2f} s"
            + (" or give a shorter ring=" if length > asked else "") + "; the music should sound right up to the end.")


def _land(song, root, chosen, chord, key, at, at_s, window, dur, kind) -> str:
    pcs, home_root = C.pitch_classes(chord, key, "ending")
    pitched = [(t, r) for t in chosen if _pitched(t) and (r := _recent(song, root, t, window, at_s) or _recent(song, root, t, 0.0, at_s))]
    if not pitched and any(_pitched(t) for t in chosen):
        _refuse("parts", "have no notes before the ending to land from", ["parts=[piano, strings]"])
    low = min(pitched, key=lambda p: sum(p[1][-1][1]) / len(p[1][-1][1]))[0] if pitched else None
    out = []
    for t, r in pitched:
        notes = C.land(r[-1][1], pcs, home_root, t is low)
        vel = round(min(1.0, sum(v for *_, v in r[-4:]) / len(r[-4:]) + (0.15 if kind == "button" else 0)), 3)
        t.note(C.names(notes, key), at=at, dur=round(dur, 4), vel=vel)
        out.append(f"{t.id} {' '.join(C.names(notes, key)) if len(notes) > 1 else C.names(notes, key)}")
    for t in chosen:
        if not _pitched(t):
            t.hit("crash", at=at, vel=0.9)
            if kind == "button":
                t.hit("kick", at=at, vel=1.0)
            out.append(f"{t.id} {'kick + crash' if kind == 'button' else 'crash'}")
    return ("held " if kind == "ring" else "struck ") + f"{dur:.2f} s: " + ", ".join(out)


def _fade(song, root, start, end):
    """The master's volume from its value at `start` down to FADE_FLOOR_DB at `end`, even in dB (points every 1/8)."""
    lane = song.master.lanes.get("volume", [])
    kept = [p for p in lane if times.seconds(p[0], root, "ending") < start - 1e-6]
    top = kept[-1][1] if kept else song.master.fields.get("volume", 1.0)      # a lane replaces the fader
    pts = [(round(start + (end - start) * i / 8, 4), round(top * 10 ** (FADE_FLOOR_DB * i / 8 / 20), 5)) for i in range(9)]
    song.master.automate("volume", kept + pts)


def scope(song) -> dict:
    song.ending = None
    return {"ending": lambda kind, at="#end", chord=None, parts=None, ring=None: ending(song, kind, at, chord, parts, ring)}
