"""Chords of the selection (sound-pro-workflows SPEC § 0, base B) and chord shapes: the one rule Chord ▾ (make,
invert), Strum and Arpeggio share.

Which selected notes are one chord: notes on one track that start together (within 30 ms of the first one) are one
chord. So are notes that were strummed: a note that starts at most 200 ms after the chord's last tone and ends where
one of its tones ends (within 10 ms) joins it, so Strum, Invert and Arpeggio find a strummed chord again and Strum
re-spaces it from its earliest start instead of stacking. A note whose pitch is a list is a chord on its own. Every
other note is a chord of one.

`shape_tones` gives the tones of a named chord shape on a root, in the key for "key" / "key7" (base C).
"""
from __future__ import annotations

from rostrum_core import codes

from ..writing import pitch as P
from . import keys
from .select_time import end_of, start_of

TOGETHER = 0.030         # seconds: tones starting this close to the first are struck together
STRUM_SPAN = 0.200       # seconds: a strummed tone starts at most this long after the tone before it …
SAME_END = 0.010         # … and ends where one of the chord's tones ends, this close
SHAPES = ("key", "key7", "major", "minor", "sus2", "sus4", "power", "octave")
NAMED = {"major": P.QUALITIES[""], "minor": P.QUALITIES["m"], "sus2": P.QUALITIES["sus2"], "sus4": P.QUALITIES["sus4"],
         "power": P.QUALITIES["5"], "octave": (0, 12)}


def of_selection(root: dict, note_ids) -> list[dict]:
    """The selected notes as chords, in time order (then by track). Each chord is a dict: "track"; "ids" (separate
    notes low to high, or the one list-pitch note); "start" / "end" (seconds: earliest start, latest end); "tones"
    (MIDI, low to high); "written" (MIDI as written: a list's order, or separate notes by start); "listed" (one note
    whose pitch is a list)."""
    wanted, by_track, out = set(note_ids), {}, []
    for track in root.get("tracks", []):
        for n in track.get("notes", []):
            if n["id"] not in wanted:
                continue
            a, b = start_of(root, n), end_of(root, n)
            if isinstance(n["pitch"], list):
                ms = keys.midis(n["pitch"])
                out.append(_row(track["id"], [n["id"]], a, b, sorted(ms), ms, True))
            else:
                by_track.setdefault(track["id"], []).append((a, b, keys.midi(n["pitch"]), n["id"]))
    for track, notes in by_track.items():
        out += [_chord(track, g) for g in group(notes)]
    return sorted(out, key=lambda c: (c["start"], c["track"]))


def _row(track, ids, start, end, tones, written, listed) -> dict:
    return {"track": track, "ids": ids, "start": start, "end": end, "tones": tones, "written": written, "listed": listed}


def group(notes: list[tuple]) -> list[list[tuple]]:
    """(start, end, …) tuples as chords (the module's rule), in time order."""
    groups: list[list[tuple]] = []
    for n in sorted(notes, key=lambda x: (x[0], x[2:])):
        g = groups[-1] if groups else None
        if g and (n[0] - g[0][0] <= TOGETHER or
                  (n[0] - g[-1][0] <= STRUM_SPAN and any(abs(n[1] - m[1]) <= SAME_END for m in g))):
            g.append(n)
        else:
            groups.append([n])
    return groups


def _chord(track: str, g: list[tuple]) -> dict:
    low = sorted(g, key=lambda x: x[2])
    return _row(track, [x[3] for x in low], g[0][0], max(x[1] for x in g), [x[2] for x in low], [x[2] for x in g], False)


def need_chords(ctx, targets) -> list[dict]:
    """The chords of 2+ tones in the selection, or a loud error when there is none."""
    for t in targets:
        ctx.item(t)                                      # an unknown id fails loudly here
    chords = [c for c in of_selection(ctx.doc, targets) if len(c["tones"]) > 1]
    if not chords:
        ctx.fail(codes.BAD_ARGUMENT, "targets", "hold no chord (two or more notes starting together, or a note with a "
                 "list of pitches)", hint="Select the notes of a chord, or make one first with note.chord.",
                 plain="Select a chord first: two or more notes that start together.")
    return chords


def shape_tones(root_midi: int, shape: str, key: str | None) -> list[int]:
    """The chord `shape` on `root_midi`, low to high (root first). "key": the key's own triad on that note, by stacking
    the key's thirds (major, minor or diminished as the key gives it); "key7" with its 7th. Those need a key, and a
    root that is a note of the key: anything else is a loud error (Fit to key first, or pick a named shape)."""
    if shape in NAMED:
        return [root_midi + i for i in NAMED[shape]]
    if shape not in ("key", "key7"):
        P.refuse("chord", f"shape {shape!r}", "is not a chord shape", [repr(s) for s in SHAPES])
    if key is None:
        P.refuse("chord", f'shape "{shape}"', "needs the song's key", ['key.add {at: 0, key: "C major"}', '"major", "minor" …'])
    pcs = P.scale(key, "chord")
    if root_midi % 12 not in pcs:
        P.refuse("chord", keys.pitch_name(root_midi, key), f"is not a note of {key}, so it has no chord in the key",
                 ['"major"', '"minor"', '"sus2"', '"sus4"', '"power"', '"octave"'], "Fit the note to the key first, or pick a named shape.")
    return [P.scale_step(root_midi, s, pcs) for s in ((0, 2, 4, 6) if shape == "key7" else (0, 2, 4))]
