"""inspect_sounds and edit_sound_cue: the agents' "Add a sound here" (UX_SPEC 3.28 Sync sound, `sound.cue`). The cue
lives in RostrumSound's song and is mixed there (rostrum2d/sound_cues.py); its time is a shared marker kept on the
layer's start, so it follows the layer. The screen's action runs the same function."""
from __future__ import annotations

from pathlib import Path

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from .. import sound_cues
from .pick import ITEM_COMP, doc_and_comp

tools = Tools()


@tools.tool("inspect_sounds", {"properties": {
    "words": {"type": "string", "description": "Words that must all appear in the sound's name, description or folders, e.g. \"whoosh soft\"."},
    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}}})
def inspect_sounds(ctx, args):
    """Recordings to tie to a layer with edit_sound_cue: RostrumSound's installed library, then the person's own sound
    folders (read-only). Each: path, about (what it is), seconds, where."""
    rows = sound_cues.choices(args.get("words", ""), int(args.get("limit", 20)))
    lines = [f'{r["about"]} ({r["seconds"]:g} s, {r["where"]}): {r["path"]}' if r.get("seconds") else
             f'{r["about"]} ({r["where"]}): {r["path"]}' for r in rows]
    return Reply(f"{len(rows)} sounds" + (":\n" + "\n".join(lines) if lines else ". Try fewer words."), {"sounds": rows})


@tools.tool("edit_sound_cue", {"required": ["layer", "sound"], "properties": {
    **ITEM_COMP,
    "layer": {"type": "string", "description": "The layer the sound belongs to: it plays at the layer's start and follows it when it moves."},
    "sound": {"type": "string", "description": "A sound file (a path from inspect_sounds)."},
    "at": {"type": "number", "default": 0, "description": "Seconds after the layer's start (may be negative: before it)."}}})
def edit_sound_cue(ctx, args):
    """Add a sound here: tie a sound to a layer. The sound goes into RostrumSound's song that plays with this scene (its
    soundtrack, else the project's main mix), on the track "Cues from 2D", timed by a shared marker "<layer> · sound" that
    stays on the layer's start whenever the layer moves, so Sound mixes it in the right place. Change its level or fades
    in RostrumSound (clip.set); 2D never mixes."""
    doc, comp = doc_and_comp(ctx, args)
    if not Path(args["sound"]).is_absolute():
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f'sound "{args["sound"]}"', "must be an absolute path",
                           hint="Find one with inspect_sounds.")
    r = sound_cues.cue(doc.folder, doc, args["layer"], args["sound"], ctx.who, float(args.get("at", 0.0)),
                       comp.get("soundtrack", ""))
    return Reply(f'Tied {Path(r["file"]).name} to {args["layer"]}: clip {r["clip"]} on "{sound_cues.TRACK_NAME}" in the '
                 f'Sound item {r["song"]}, at {r["at"]} (the marker follows the layer). RostrumSound mixes it.', r)
