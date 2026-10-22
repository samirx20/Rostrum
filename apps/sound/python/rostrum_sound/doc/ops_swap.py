"""`clip.swap {media}`: put another file in place of the selected clips, keeping where they sit, how long they play,
their level and fades (and their layer group). The new file starts from its beginning, or at `in` (the old in-point means
nothing in a different file) and a file shorter than the spot just plays shorter. `match` (default on) sets the
level so the new sound is as loud as the one it replaces, measured over the part that plays; a silent file on either
side leaves the level as it was. One call = one undo step (Esc on the screen puts the old one back by undo).
"""
from __future__ import annotations

import dataclasses

from rostrum_core import Param, codes

from . import fields as FD
from . import values as V
from .registry import REGISTRY
from .select_time import clip_length, file_seconds, length_like, speed, start_of

MEDIA = dataclasses.replace(next(p for p in FD.params("clip") if p.name == "media"), required=True,
                            help="The file that takes the place of each selected clip's.")
IN = V.N("in", 0, None, "Swap", "s", "secondary", label="Start in the file",
         help="Where in the new file the sound starts (default: its beginning; a library result is a stretch of a file).")
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
                    params=[MEDIA, IN, MATCH], label="Swap sound", importance="primary")
def swap(ctx, targets, args):
    root, media = ctx.doc, args["media"]
    for t in targets:
        c = ctx.item(t)
        start = float(args.get("in", 0))
        new = {**c, "media": media, "in": start}
        try:
            room = file_seconds(new) - start
        except Exception as e:  # noqa: BLE001
            ctx.fail(codes.BAD_ARGUMENT, "media", f"could not be read: {e}")
        source = min(clip_length(c, root) * speed(c), room)
        if source <= 1e-3:
            ctx.fail(codes.BAD_ARGUMENT, "media", f'has no sound to put in clip "{t}"')
        if args.get("match", True) and c.get("media"):
            try:
                was = _loudness(c["media"], float(c.get("in", 0)), min(clip_length(c, root) * speed(c), file_seconds(c)))
            except Exception:  # noqa: BLE001  (an unreadable old file: nothing to match)
                was = None
            now = _loudness(media, start, source)
            if was is not None and now is not None:
                ctx.set(t, "volume", round(min(4.0, float(c.get("volume", 1)) * 10 ** ((was - now) / 20)), 4))
        ctx.set(t, "media", media)
        ctx.set(t, "in", start)
        ctx.set(t, "length", length_like(c.get("length"), source, root, start_of(root, c), {**new, "id": t}))
