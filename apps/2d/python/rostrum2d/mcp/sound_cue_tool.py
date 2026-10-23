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
    **ITEM_COMP,
    "words": {"type": "string", "description": "Words that must all appear in a recording's name, description or folders, e.g. \"cello pizzicato\". Empty: the song's instruments first (a note or hit on the moment), then the person's recordings."},
    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}}})
def inspect_sounds(ctx, args):
    """What to tie to a layer with edit_sound_cue, music first: with no words, a note or a hit on the song's own
    instruments ("note:<track>" / "hit:<track>"), then the person's own recordings; with words, their recordings, then
    RostrumSound's installed library. Most moves need no sound; a note on the landing or a string / cymbal rise into it
    (edit_sounds_from_motion in RostrumSound) beats an effect. Each: path, about (what it is), seconds, where."""
    doc, comp = doc_and_comp(ctx, args)
    rows = sound_cues.choices(args.get("words", ""), int(args.get("limit", 20)), doc.folder, comp.get("soundtrack", ""))
    lines = [f'{r["about"]} ({r["seconds"]:g} s, {r["where"]}): {r["path"]}' if r.get("seconds") else
             f'{r["about"]} ({r["where"]}): {r["path"]}' for r in rows]
    return Reply(f"{len(rows)} sounds" + (":\n" + "\n".join(lines) if lines else ". Try fewer words."), {"sounds": rows})


@tools.tool("edit_sound_cue", {"required": ["layer", "sound"], "properties": {
    **ITEM_COMP,
    "layer": {"type": "string", "description": "The layer the sound belongs to: it plays at the layer's start and follows it when it moves."},
    "sound": {"type": "string", "description": "A path from inspect_sounds: \"note:<track>\" / \"hit:<track>\" (struck on the song's instrument) or a sound file."},
    "at": {"type": "number", "default": 0, "description": "Seconds after the layer's start (may be negative: before it)."}}})
def edit_sound_cue(ctx, args):
    """Add a sound here: tie a sound to a layer. The sound goes into RostrumSound's song that plays with this scene (its
    soundtrack, else the project's main mix), on the track "Cues from 2D", timed by a shared marker "<layer> · sound" that
    stays on the layer's start whenever the layer moves, so Sound mixes it in the right place. Change its level or fades
    in RostrumSound (clip.set); 2D never mixes."""
    doc, comp = doc_and_comp(ctx, args)
    if not sound_cues.sound_cue_music.is_music(args["sound"]) and not Path(args["sound"]).is_absolute():
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f'sound "{args["sound"]}"', "must be an absolute path",
                           hint="Find one with inspect_sounds.")
    r = sound_cues.cue(doc.folder, doc, args["layer"], args["sound"], ctx.who, float(args.get("at", 0.0)),
                       comp.get("soundtrack", ""), group=ctx.group)          # in the agent's group: its Undo takes it too
    what = f'a {r["music"].split(":")[0]}' if r["music"] else f'clip {r["clip"]}'
    return Reply(f'Tied {r["music"] or Path(r["file"]).name} to {args["layer"]}: {what} on track "{r["track"]}" in the '
                 f'Sound item {r["song"]}, at {r["at"]} (the marker follows the layer). RostrumSound mixes it.', r)
