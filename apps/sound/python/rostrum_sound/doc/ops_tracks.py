"""Tracks and the document's own settings: track.add / set / remove / lock / unlock, doc.set. A locked track
(`locked`) refuses every change to it and its items (rostrum_core/locks.py: one lock check for every app)."""
from __future__ import annotations

from rostrum_core import PLUGIN_ITEM, Param, codes
from rostrum_core.edits import MISSING
from rostrum_core import ids as core_ids

from . import fields as FD
from . import sounds
from .registry import REGISTRY, set_fields, taken

REGISTRY.operation("doc.set", "Change the tempo, length, beats per bar or sample rate of the song. Its target is the id [\"root\"] (the target column names item types, not ids).", target="doc",
                   params=FD.params("doc"), label="Edit song", fields=True)(set_fields)


def sound_fields(ctx, track_id, key) -> dict:
    """What `sound: key` sets on that track: the instrument form and its field, and the name when it still follows the
    sound (the person's own name stays). Never stored itself."""
    track = ctx.item(track_id)
    if not sounds.known(key):
        ctx.fail(codes.BAD_ARGUMENT, f"sound={key!r}", "is not a sound", sounds.KEYS)
    if sounds.canonical(key) not in sounds.allowed(track):
        ctx.fail(codes.BAD_ARGUMENT, f"sound={key!r}", f"can't play track {track_id}'s notes, hits or lines",
                 sounds.allowed(track), "Notes need an instrument, hits the drum kit, lines a voice.")
    out = sounds.fields(key)
    if sounds.follows(track):
        out["name"] = sounds.default_name(key)
    return out


@REGISTRY.operation("track.set", "Change a track's sound (sound: a plain recorded instrument, a synth preset, the synth, a modelled instrument, a "
                    "drum kit or a voice, e.g. \"builtIn:piano\", \"builtIn:warmPad\", \"synth\", \"model:guitar\", \"kit:studio\", \"voice:ryan\"; the notes stay "
                    "and the name follows unless it was renamed), level, pan, reverb, tone, mute or solo.",
                    target="track", params=FD.params("track"), label="Edit track", fields=True)
def track_set(ctx, targets, args):
    args = dict(args)
    key = args.pop("sound", None)
    for t in targets:
        change = {**sound_fields(ctx, t, key), **args} if key else args
        for k, v in change.items():
            ctx.set(t, k, v)


@REGISTRY.operation("track.add", "Add a track (choose its instrument in the same call).", label="Add track",
                    params=[Param.text("id", label="Id", help="Optional; counted when left out (track_1 …)."),
                            *FD.params("track")])
def track_add(ctx, targets, args):
    args = dict(args)
    id_ = args.pop("id", None) or core_ids.counted(taken(ctx), "track")
    if id_ in taken(ctx):
        ctx.fail(codes.BAD_ARGUMENT, f'id "{id_}"', "is already used in this document")
    ctx.insert("root", "tracks", {"id": id_, "type": "track", "name": args.pop("name", id_),
                                  **FD.DEFAULTS["track"], **args})


@REGISTRY.operation("track.remove", "Delete tracks and everything on them (also an item of a plugin this Rostrum doesn't have).",
                    target=("track", PLUGIN_ITEM), label="Delete track",
                    importance="secondary")
def track_remove(ctx, targets, args):
    for t in targets:
        ctx.remove(t)


@REGISTRY.operation("track.lock", "Lock tracks: nobody can change them or anything on them (people, agents, scripts) "
                    "until they are unlocked (also an item of a plugin this Rostrum doesn't have).",
                    target=("track", PLUGIN_ITEM), label="Lock track",
                    valid_when={"not": {"is": ["locked", True]}})
def track_lock(ctx, targets, args):
    for t in targets:
        ctx.set(t, "locked", True)


@REGISTRY.operation("track.unlock", "Unlock tracks so they can be changed again.", target=("track", PLUGIN_ITEM),
                    label="Unlock track", valid_when={"is": ["locked", True]})
def track_unlock(ctx, targets, args):
    for t in targets:
        ctx.set(t, "locked", MISSING)
