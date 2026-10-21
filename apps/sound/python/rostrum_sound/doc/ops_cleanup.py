"""clip.split_stems: a clip becomes four tracks, one per stem (vocals, drums, bass, other), each holding a copy of the
clip that plays that stem (`stem` set; the cleaned takes are made by the render_cleanup tool). One history step.

The original clip stays where it is with its volume set to 0, so the stems are not heard twice. Why the clip and
not its track's mute: it touches only the clip being split (the track's other clips and anything added to it later
keep playing), works the same whatever else the track holds, and the clip's level is not lost, since every stem copy
keeps it. Each stem track is `<clip id>.<stem>`, so a second split of the same clip fails instead of duplicating.
"""
from __future__ import annotations

from rostrum_core import codes
from rostrum_core.tree import index

from ..cleanup import STEMS
from . import fields as FD
from . import ids
from .registry import LISTS, REGISTRY, taken

TRACK_MIX = ("volume", "pan", "reverb", "tone", "output")   # the stem tracks sound like the original track
NOT_COPIED = ("id", "type", "group", "effects", "isolate")


def stem_track_ids(clip_id: str) -> list[str]:
    return [f"{clip_id}.{s}" for s in STEMS]


@REGISTRY.operation("clip.split_stems", "Split a clip into four new tracks, one per stem (vocals, drums, bass, other), "
                    "each with a copy of the clip playing that stem; the original clip's volume goes to 0. Make the "
                    "stems' audio afterwards with the render_cleanup tool.", target="clip", label="Split into stems",
                    importance="secondary")
def split_stems(ctx, targets, args):
    for clip_id in targets:
        loc = index(ctx.doc, LISTS)[clip_id]
        track, clip = ctx.item(loc.parent), loc.item
        have = [t for t in stem_track_ids(clip_id) if t in taken(ctx)]
        if have:
            ctx.fail(codes.BAD_ARGUMENT, f'clip "{clip_id}"', f"is already split into stems ({', '.join(have)})",
                     hint="Delete those tracks first (track.remove) to split it again.")
        at = [t["id"] for t in ctx.doc["tracks"]].index(track["id"]) + 1
        for n, (stem, tid) in enumerate(zip(STEMS, stem_track_ids(clip_id))):
            ctx.insert("root", "tracks", {"id": tid, "type": "track", **FD.DEFAULTS["track"],
                                          **{k: track[k] for k in TRACK_MIX if k in track},
                                          "name": f"{track.get('name', track['id'])} · {stem}"}, index=at + n)
            copy = {k: v for k, v in clip.items() if k not in NOT_COPIED}
            cid = ids.clip(tid, clip["at"], ctx.doc, taken(ctx), ctx.where)
            ctx.insert(tid, "clips", {"id": cid, "type": "clip", **copy, "stem": stem, "useCleaned": True})
        ctx.set(clip_id, "volume", 0)
