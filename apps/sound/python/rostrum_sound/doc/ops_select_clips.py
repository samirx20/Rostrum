"""Cut and join the selected clips: `clip.split` (at a time), `clip.join` (clips cut from one file, back to back,
become one), `clip.crossfade` (neighbours overlap and fade across), `clip.normalize` (set the level so the
loudest peak reaches a target). Each one operation over the selection, one undo step. A new clip's id comes from
where it starts (`ids.clip`); a copy's effects get new ids; a clip's other times keep their form.
"""
from __future__ import annotations

import copy

from rostrum_core import Param, codes
from rostrum_core.edits import MISSING

from . import ids, times
from . import values as V
from .registry import REGISTRY, taken
from .select_time import (clip_length, file_seconds, length_like, need_same_kind, source_length, speed,
                          start_of)

AT = V.time("at", required=True, group="Split", label="Split at", help="The time to cut at: seconds, a beat, or a "
            'marker ("#drop"). Every selected clip that plays through that time becomes two.')
FADE = V.N("length", 0.001, 5, "Crossfade", "s", default=0.05, label="Overlap",
           help="How long the two clips overlap while one fades out and the other in. Left out = 0.05 s.")
PEAK = V.N("peak", -60, 0, "Level", "dB", default=-1, label="Peak",
           help="The loudest moment of each clip (the part that plays) ends up this loud, in dB under full scale. "
                "Left out = -1.")
SAME = ("media", "volume", "pitch", "shift", "stretch", "pan", "panTo", "reverb", "stem", "isolate", "denoise",
        "dereverb", "useCleaned")


def _sorted(ctx, targets):
    return sorted((ctx.item(t) for t in targets), key=lambda c: start_of(ctx.doc, c))


def _new_effect_ids(clip):
    used = {clip["id"]}
    for e in clip.get("effects", []):
        e["id"] = ids.effect(clip["id"], e.get("effect", "effect"), used)
        used.add(e["id"])


@REGISTRY.operation("clip.split", "Cut the selected clips in two at a time. Fades stay on the outer ends; every "
                    "clip that plays through that time is cut, the others are left alone.", target="clip",
                    params=[AT], label="Split clip")
def split(ctx, targets, args):
    root, t = ctx.doc, times.seconds(args["at"], ctx.doc, "split")
    cut = [c for c in (ctx.item(x) for x in targets)
           if start_of(root, c) + 1e-6 < t < start_of(root, c) + clip_length(c, root) - 1e-6]
    if not cut:
        ctx.fail(codes.BAD_ARGUMENT, "at", f"is not inside any selected clip ({t:.3f} s)",
                 hint="Put the cut inside a clip: after it starts and before it ends.")
    for c in cut:
        start, track = start_of(root, c), ctx.idx[c["id"]].parent
        done = (t - start) * speed(c)                           # seconds of the file before the cut
        total = source_length(c, root)
        right = copy.deepcopy(c)
        right.update(at=args["at"], **{"in": round(float(c.get("in", 0)) + done, 4)})
        right["id"] = ids.clip(track, args["at"], root, taken(ctx))
        if c.get("length") is not None:
            right["length"] = length_like(c["length"], total - done, root, t, right)
        if "fadeIn" in right:
            right["fadeIn"] = 0
        if "panTo" in c:                                        # the pan sweep carries on across the cut
            mid = round(c.get("pan", 0) + (c["panTo"] - c.get("pan", 0)) * done / total, 4)
            right["pan"] = mid
            ctx.set(c["id"], "panTo", mid)
        _new_effect_ids(right)
        ctx.set(c["id"], "length", length_like(c.get("length"), done, root, start, c))
        if "fadeOut" in c:
            ctx.set(c["id"], "fadeOut", 0)
        ctx.insert(track, "clips", right, ctx.idx[c["id"]].index + 1)


def _differences(a, b):
    diff = [k for k in SAME if a.get(k) != b.get(k)]
    bare = lambda c: [{k: v for k, v in e.items() if k != "id"} for e in c.get("effects", [])]  # noqa: E731
    return diff + (["effects"] if bare(a) != bare(b) else [])


@REGISTRY.operation("clip.join", "Join clips of one track that play one file back to back (cut with clip.split) "
                    "into one clip.", target="clip", label="Join clips", importance="secondary")
def join(ctx, targets, args):
    root = ctx.doc
    if len(targets) < 2:
        ctx.fail(codes.BAD_ARGUMENT, "target", "needs two or more clips to join")
    need_same_kind(ctx, targets, "join")
    clips = _sorted(ctx, targets)
    hint = "Select clips cut from one file that follow each other; to blend two different clips use clip.crossfade."
    for a, b in zip(clips, clips[1:]):
        if diff := _differences(a, b):
            ctx.fail(codes.CONFLICT, f'clips "{a["id"]}" and "{b["id"]}"',
                     "are not the same sound: they differ in " + ", ".join(diff), hint=hint)
        end_t, end_in = start_of(root, a) + clip_length(a, root), float(a.get("in", 0)) + source_length(a, root)
        if abs(end_t - start_of(root, b)) > 1e-3 or abs(end_in - float(b.get("in", 0))) > 1e-3:
            ctx.fail(codes.CONFLICT, f'clips "{a["id"]}" and "{b["id"]}"', "do not follow each other (a gap, an "
                     "overlap, or the file does not continue where the first stops)", hint=hint)
    first, last = clips[0], clips[-1]
    if last.get("length") is None:
        if "length" in first:
            ctx.set(first["id"], "length", MISSING)
    else:
        total = sum(source_length(c, root) for c in clips)
        ctx.set(first["id"], "length", length_like(first.get("length"), total, root, start_of(root, first), first))
    if "fadeOut" in last:
        ctx.set(first["id"], "fadeOut", last["fadeOut"])
    for c in clips[1:]:
        ctx.remove(c["id"])


@REGISTRY.operation("clip.crossfade", "Blend neighbouring clips of one track: the first runs on under the next "
                    "for a moment while it fades out and the next fades in. The later clip does not move.",
                    target="clip", params=[FADE], label="Crossfade", importance="secondary")
def crossfade(ctx, targets, args):
    root, n = ctx.doc, args.get("length", 0.05)
    if len(targets) < 2:
        ctx.fail(codes.BAD_ARGUMENT, "target", "needs two or more neighbouring clips")
    need_same_kind(ctx, targets, "crossfade")
    clips = _sorted(ctx, targets)
    for a, b in zip(clips, clips[1:]):
        want = start_of(root, b) + n - start_of(root, a)           # the first plays until just after the next starts
        if want <= 1e-6:
            ctx.fail(codes.BAD_ARGUMENT, f'clips "{a["id"]}" and "{b["id"]}"',
                     "are not neighbours in time (the second starts before the first)",
                     hint="Select clips that follow each other.")
        src = want * speed(a)
        if float(a.get("in", 0)) + src > file_seconds(a) + 1e-3:
            ctx.fail(codes.CHECK_FAILED, f'clip "{a["id"]}"', "has no more sound after its end to fade over",
                     hint="Use a shorter overlap, or move the clips closer.")
        ctx.set(a["id"], "length", length_like(a.get("length"), src, root, start_of(root, a), a))
        ctx.set(a["id"], "fadeOut", n)
        ctx.set(b["id"], "fadeIn", n)


BY = Param.choice("by", ["peak", "loudness"], default="peak", group="Level", label="By",
                  labels={"peak": "Loudest moment", "loudness": "Loudness"},
                  help='"peak": the loudest moment reaches `peak`; "loudness": every clip sounds as loud (`loudness`, '
                       "LUFS: even out a voice-over's takes).")
LOUD = V.N("loudness", -40, -6, "Level", "LUFS", label="Loudness",
           help="The loudness every clip ends at (by loudness). Left out = the middle of the selected clips' own "
                "loudness (the fewest big changes).")


@REGISTRY.operation("clip.normalize", "Set each selected clip's level: by its loudest moment (to a target peak, "
                    "default -1 dB) or by loudness (every clip as loud: given, or the middle of theirs). Only the part "
                    "that plays counts.", target="clip", params=[PEAK, BY, LOUD], label="Normalize clips",
                    importance="secondary")
def normalize(ctx, targets, args):
    import numpy as np

    peak, heard = args.get("peak", -1), {t: _heard(ctx, t) for t in targets}
    if args.get("by") == "loudness":
        from ..listen.bs1770 import integrated
        lufs = {t: integrated(x, sr) for t, (x, sr) in heard.items()}
        bad = [t for t, v in lufs.items() if not np.isfinite(v)]
        if bad:
            ctx.fail(codes.CHECK_FAILED, f'clip "{bad[0]}"', "is too short or too quiet to measure its loudness")
        aim = args.get("loudness", float(np.median(list(lufs.values()))))
        gains = {t: 10 ** ((aim - v) / 20) for t, v in lufs.items()}
    else:
        gains = {t: 10 ** (peak / 20) / float(np.abs(x).max()) for t, (x, _) in heard.items()}
    for t, volume in gains.items():
        if volume > 4:
            ctx.fail(codes.CHECK_FAILED, f'clip "{t}"', f"is too quiet to reach that level (it would need ×{volume:.1f}"
                     ", the most a clip takes is ×4)", hint="Choose a lower level.")
        ctx.set(t, "volume", round(volume, 4))


def _heard(ctx, t):
    """(samples, rate) of the part of clip `t` that plays; a silent or unreadable clip is a loud error."""
    import numpy as np
    import soundfile as sf

    from ..clean_clips import media_of
    c = ctx.item(t)
    try:
        with sf.SoundFile(str(media_of(c, t))) as f:
            sr = f.samplerate
            f.seek(min(int(float(c.get("in", 0)) * sr), f.frames))
            x = f.read(int(source_length(c, ctx.doc) * sr), dtype="float32", always_2d=True)
    except RuntimeError as e:
        ctx.fail(codes.BAD_ARGUMENT, f'clip "{t}" media', f"could not be read: {e}")
    if not x.size or float(np.abs(x).max()) <= 1e-6:
        ctx.fail(codes.CHECK_FAILED, f'clip "{t}"', "is silent in the part that plays, so it can't be normalized")
    return x, sr
