"""`note.chord` and `note.invert` (sound-pro-workflows SPEC § 3.9): Chord ▾ › Make a chord and Invert up / down.

Make a chord: each selected note is a root; the chord's other tones are added as separate notes (same start, length,
velocity and playing; new ids), each spelled in the key playing then. A chord is what a person sees: a stack of notes
that can each be edited. Invert works on the chords of the selection (`chords.py`, base B). Both fail whole, changing
nothing, when a tone would go past the 128 MIDI keys (0 to 127).
"""
from __future__ import annotations

import copy

from rostrum_core import Param, codes

from . import chords, ids, keys
from .ops_transpose import NO_KEY, _shifted
from .registry import REGISTRY, taken
from .select_time import start_of

SHAPE = Param.choice("shape", list(chords.SHAPES), required=True, group="Chord", label="Chord",
                     labels={"key": "In key", "key7": "In key with 7th", "major": "Major", "minor": "Minor", "sus2": "Sus2",
                             "sus4": "Sus4", "power": "Power (5th)", "octave": "Octave"},
                     help="key: the key's own chord on the note (major, minor or diminished, as the key gives it; the note "
                          "must be in the key); key7: the same with its 7th; or a named shape.")
INVERSION = Param.number("inversion", min=0, max=3, integer=True, default=0, group="Chord", label="Inversion",
                         help="0 = root position, the other tones above the note; 1 = the chord's 3rd lowest, 2 = its 5th "
                              "lowest, 3 = its 7th lowest. The selected note stays where it is; the other tones go round it.")
BY = Param.number("by", min=-3, max=3, integer=True, required=True, group="Invert", label="By",
                  help="+1: the lowest note goes up an octave; −1: the top note goes down an octave; ±2, ±3 repeat it. Not 0.")


def _voiced(root_midi: int, shape: str, key, inversion: int) -> list[int]:
    """The chord's tones with `inversion` tones moved up an octave, placed so the root stays on `root_midi`."""
    tones = chords.shape_tones(root_midi, shape, key)
    k = inversion % len(tones)
    turned = tones[k:] + [m + 12 for m in tones[:k]]
    by = root_midi - next(m for m in turned if m % 12 == root_midi % 12 and (m - root_midi) % 12 == 0)
    return [m + by for m in turned]


@REGISTRY.operation("note.chord", "Build a chord on each selected note: its other tones are added as separate notes "
                    "(same start, length and velocity; the selected note stays). `shape` \"key\" = the key's own chord on "
                    "that note (D in C major gives D-F-A, B gives B-D-F), \"key7\" with its 7th, or major, minor, sus2, "
                    "sus4, power, octave; `inversion` 1-3 puts the 3rd, 5th or 7th lowest. Valid on notes of a pitched "
                    "track; \"key\" and \"key7\" need the song's key and a note in it. Tones already sounding there are not "
                    "doubled. The reply lists the added notes. Past the 128 MIDI keys (0 to 127) it fails and changes nothing.",
                    target="note", params=[SHAPE, INVERSION], label="Make a chord", importance="secondary")
def chord(ctx, targets, args):
    shape, inversion, root = args["shape"], args.get("inversion", 0), ctx.doc
    plan = []
    for t in targets:
        n = ctx.item(t)
        sec = start_of(root, n)
        key = keys.key_for(root, sec)
        if shape in ("key", "key7") and not key:
            ctx.fail(codes.BAD_ARGUMENT, "shape", NO_KEY.replace("transpose in half steps", "pick a named shape"),
                     hint='Set a key (key.add {at: 0, key: "C major"}) or use "major", "minor" ….', plain="The song has no key.")
        low = min(keys.midis(n["pitch"]))
        tones = _voiced(low, shape, key, inversion)
        if not all(0 <= m <= 127 for m in tones):
            ctx.fail(codes.BAD_ARGUMENT, f'"{t}"', "would have tones outside the 128 MIDI keys (0 to 127)", hint="Use a lower inversion or another note.")
        track = ctx.idx[t].parent
        sounding = {m for o in ctx.item(track)["notes"] if abs(start_of(root, o) - sec) <= chords.TOGETHER
                    for m in keys.midis(o["pitch"])}
        plan += [(track, n, m, key) for m in tones if m not in sounding]
    for track, n, m, key in plan:                        # all checked first: a failure changes nothing
        new = {k: copy.deepcopy(v) for k, v in n.items() if k not in ("id", "pitch")}
        new.update(id=ids.note(track, n["at"], ctx.doc, taken(ctx), ctx.where),
                   pitch=m if isinstance(n["pitch"], int) else keys.pitch_name(m, key))
        ctx.insert(track, "notes", new)


@REGISTRY.operation("note.invert", "Invert each chord of the selection (notes starting together, a strummed chord, or a "
                    "note with a list of pitches): `by` +1 moves the lowest note up an octave, -1 the top note down an "
                    "octave, ±2 / ±3 repeat it. Valid when the selection holds a chord of two or more notes. The reply "
                    "lists the notes whose pitch changed. Past the 128 MIDI keys (0 to 127) it fails and changes nothing.",
                    target="note", params=[BY], label="Invert", importance="secondary")
def invert(ctx, targets, args):
    by = args["by"]
    if by == 0:
        ctx.fail(codes.BAD_ARGUMENT, "by", "is 0", ["1", "-1", "2", "-2", "3", "-3"], hint="+1 inverts up, -1 down.")
    plan = []
    for c in chords.need_chords(ctx, targets):
        if c["listed"]:
            pitch = list(ctx.item(c["ids"][0])["pitch"])
            for _ in range(abs(by)):
                order = sorted(range(len(pitch)), key=lambda i: keys.midi(pitch[i]))
                i = order[0] if by > 0 else order[-1]
                pitch[i] = _moved(ctx, c["ids"][0], pitch[i], 12 if by > 0 else -12)
            plan.append((c["ids"][0], sorted(pitch, key=keys.midi)))
            continue
        now = {t: ctx.item(t)["pitch"] for t in c["ids"]}
        for _ in range(abs(by)):
            t = (min if by > 0 else max)(now, key=lambda x: keys.midi(now[x]))
            now[t] = _moved(ctx, t, now[t], 12 if by > 0 else -12)
        plan += list(now.items())
    for t, pitch in plan:
        ctx.set(t, "pitch", pitch)


def _moved(ctx, t, p, by):
    try:
        return _shifted(p, by)
    except ValueError:
        ctx.fail(codes.BAD_ARGUMENT, f'"{t}"', "would go outside the 128 MIDI keys (0 to 127)", hint="Invert the other way.")
