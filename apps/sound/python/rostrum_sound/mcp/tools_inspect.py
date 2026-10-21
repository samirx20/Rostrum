"""Sound's own inspect tools: what the engine accepts, what an instrument can play, what sounds are installed."""
from __future__ import annotations

from rostrum_core import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from .. import library


def _instrument(args) -> dict:
    forms = [k for k in ("builtIn", "sfz", "kit", "kitSfz") if args.get(k)]
    if len(forms) != 1:
        raise RostrumError(codes.BAD_ARGUMENT, "inspect_instrument", "the instrument", "needs exactly one of builtIn, sfz, kit, kitSfz",
                           ["builtIn", "sfz", "kit", "kitSfz"])
    return {forms[0]: args[forms[0]]}


def register(tools: Tools):
    @tools.tool("inspect_engine", {"properties": {}})
    def inspect_engine(ctx, args):
        """Every name the sound engine accepts: tones, reverb spaces, EQ shapes, built-in instruments, drum names, effects with their fields and defaults."""
        d = ctx.app.state.engine.request("describe")
        return Reply(f"Engine {d['engine']}, contract {d['contract']}: {len(d['builtIns'])} built-in instruments, "
                     f"{len(d['effects'])} effect types, {len(d['spaces'])} reverb spaces.", d)

    @tools.tool("inspect_instrument", {"properties": {
        "builtIn": {"type": "string"}, "sfz": {"type": "string", "description": "Absolute path to an .sfz file."},
        "kit": {"type": "string", "enum": ["synth"]}, "kitSfz": {"type": "string"}}})
    def inspect_instrument(ctx, args):
        """What an instrument can play before you write for it: its lowest and highest note, gaps, velocity layers, or a kit's drum names."""
        r = ctx.app.state.engine.request("range", instrument=_instrument(args))
        if r.get("low"):
            gaps = f", {len(r['gaps'])} gaps" if r.get("gaps") else ""
            return Reply(f"Plays {r['low']}–{r['high']}{gaps}, {r.get('layers', 1)} velocity layers.", r)
        return Reply(f"Drums: {', '.join(r['drums'])}.", r)

    @tools.tool("inspect_library", {"properties": {
        "find": {"type": "string", "description": "Words that must appear in the path or the description (case-insensitive), e.g. \"cello\" or \"door slam\"."},
        "kind": {"type": "string", "enum": ["instruments", "recordings"], "default": "instruments"},
        "limit": {"type": "integer", "default": 40, "minimum": 1, "maximum": 400}}})
    def inspect_library(ctx, args):
        """Installed sounds under ~/.rostrum/assets/sounds: SFZ instruments or recordings (WAV / FLAC / OGG / MP3), each with its absolute path, what it is (`about`: the pack's own title, else its folder and file words), its category when the pack has one, and for recordings its length in seconds."""
        kind, words = args.get("kind", "instruments"), args.get("find") or ""
        try:
            found = library.find(kind, words)
        except FileNotFoundError as e:
            raise RostrumError(codes.NOT_FOUND, "inspect_library", str(library.LIBRARY), "is not installed") from e
        limit = args.get("limit", 40)
        shown = f", showing the first {limit} (raise limit or narrow find)" if len(found) > limit else ""
        sounds = [library.describe(p) for p in found[:limit]]
        return Reply(f"{len(found)} {kind} found" + (f" for \"{words}\"" if words else "") + f" under {library.LIBRARY}{shown}.",
                     {"sounds": sounds, "total": len(found), "more": len(found) > limit})
