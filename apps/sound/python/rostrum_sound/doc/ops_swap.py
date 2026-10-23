"""`clip.swap {media}`: put another file in place of the selected clips, keeping where they sit, how long they play,
their level and fades (and their layer group). The new file starts from its beginning, or at `in` (the old in-point means
nothing in a different file) and a file shorter than the spot just plays shorter. `match` (default on) sets the
level so the new sound is as loud as the one it replaces, measured over the part that plays; a silent file on either
side leaves the level as it was. One call = one undo step.

Stepping through candidates (the screen's ↑ / ↓): every step must swap from the ORIGINAL clip, never from the last
candidate (a shorter file would shorten the spot for good, and the level would drift). The `was_*` values say what the
original was (its file, in-point, level and how much of the file played); with them the clip's current state is
ignored, so step after step gives the same answer as swapping the original once.
"""
from __future__ import annotations

import dataclasses

from rostrum_core import Param, codes

from . import fields as FD
from . import media as media_of
from . import values as V
from .registry import REGISTRY
from .select_time import clip_length, file_seconds, length_like, source_length, speed, start_of

MEDIA = dataclasses.replace(next(p for p in FD.params("clip") if p.name == "media"), required=True,
                            help="The file that takes the place of each selected clip's.")
IN = V.N("in", 0, None, "Swap", "s", "secondary", label="Start in the file",
         help="Where in the new file the sound starts (default: its beginning; a library result is a stretch of a file).")
WAS = dict(group="Swap again", importance="deep",
           help="Swapping again from the original: the clip is taken to be as these say, not as it is now.")
WAS_MEDIA = Param.text("was_media", label="Original file", **WAS)
WAS_IN = Param.number("was_in", min=0, unit=" s", label="Original start in its file", **WAS)
WAS_LENGTH = Param.number("was_length", min=0, unit=" s", label="Original length (seconds of its file)", **WAS)
WAS_VOLUME = Param.number("was_volume", min=0, max=4, label="Original level", **WAS)
MATCH = Param.toggle("match", default=True, group="Swap", label="Match the level",
                     help="Set the level so the new sound is as loud as the one it replaces (measured).")


def _loudness(path, start: float, seconds: float):
    """Integrated loudness (LUFS) of `seconds` of `path` from `start`, or None when silent or too short."""
    import numpy as np
    import soundfile as sf

    from ..listen.bs1770 import integrated
    with sf.SoundFile(str(path)) as f:
        f.seek(min(int(start * f.samplerate), f.frames))
        x = f.read(int(seconds * f.samplerate), dtype="float32", always_2d=True)
        rate = f.samplerate
    if not x.size or float(np.abs(x).max()) <= 1e-6:
        return None
    v = integrated(x, rate)
    return float(v) if np.isfinite(v) else None


@REGISTRY.operation("clip.swap", "Put another file in place of the selected clips: same start, same length (a shorter "
                    "file plays shorter), same level (matched by loudness) and fades.", target="clip",
                    params=[MEDIA, IN, MATCH, WAS_MEDIA, WAS_IN, WAS_LENGTH, WAS_VOLUME], label="Swap sound", importance="primary")
def swap(ctx, targets, args):
    root, media = ctx.doc, args["media"]
    for t in targets:
        c = _original(ctx.item(t), args)
        start = float(args.get("in", 0))
        new = {**c, "media": media, "in": start}
        try:
            room = file_seconds(new) - start
        except Exception as e:  # noqa: BLE001
            ctx.fail(codes.BAD_ARGUMENT, "media", f"could not be read: {e}")
        source = min(clip_length(c, root) * speed(c), room)
        if source <= 1e-3:
            ctx.fail(codes.BAD_ARGUMENT, "media", f'has no sound to put in clip "{t}"')
        if "was_media" in args:                          # swapping again: the level starts from the original's
            ctx.set(t, "volume", c["volume"])
        if args.get("match", True) and c.get("media"):
            try:
                was = _loudness(media_of.file(c["media"]), float(c.get("in", 0)), min(clip_length(c, root) * speed(c), file_seconds(c)))
            except Exception:  # noqa: BLE001  (an unreadable old file: nothing to match)
                was = None
            now = _loudness(media_of.file(media), start, source)
            if was is not None and now is not None:
                ctx.set(t, "volume", round(min(4.0, float(c.get("volume", 1)) * 10 ** ((was - now) / 20)), 4))
        ctx.set(t, "media", media)
        ctx.set(t, "in", start)
        ctx.set(t, "length", length_like(c.get("length"), source, root, start_of(root, c), {**new, "id": t}))


def _original(c: dict, args: dict) -> dict:
    """The clip as the swap should see it: as it is, or (swapping again) as the original `was_*` values say."""
    if "was_media" not in args:
        return c
    was = {"media": args["was_media"], "in": args.get("was_in", 0), "volume": args.get("was_volume", c.get("volume", 1))}
    if "was_length" in args:
        was["length"] = args["was_length"]
    else:
        was["length"] = None
    return {**c, **was}


def original_args(clip: dict, root: dict) -> dict:
    """The `was_*` arguments that say what `clip` is now, for stepping through candidates from it."""
    return {"was_media": clip["media"], "was_in": float(clip.get("in", 0)), "was_length": round(source_length(clip, root), 4),
            "was_volume": float(clip.get("volume", 1))}
