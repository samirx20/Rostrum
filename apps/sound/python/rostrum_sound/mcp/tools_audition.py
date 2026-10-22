"""render_audition: hear a Library entry (an instrument, a drum kit, a designed sound, a sound file) through the
engine, on the track's own notes when one is given. The document is not touched; the WAV is kept by content."""
from __future__ import annotations

from rostrum_core import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from .. import audition
from ..builder import INSTRUMENT_KEYS

ENTRY = {"type": "object", "description": (
    "What to hear. An instrument: {instrument: builtIn|synth|model|sfz|plugin, builtIn|model|sfz|plugin: name}; a drum kit: {instrument: kit} "
    "or {instrument: kitSfz, kitSfz: path}; a designed sound: {design: whoosh|click|riser|hit|subDrop, …its fields}; a sound file: "
    "{media: absolute path, in: seconds, length: seconds}. Omit it (with `track`) to hear the track's own sound.")}


def register(tools: Tools):
    @tools.tool("render_audition", {"properties": {
        "item": {"type": "string", "description": "The Sound document's item id. Optional when only one is open."},
        "entry": ENTRY,
        "track": {"type": "string", "description": "A track id: an instrument or kit plays this track's own notes (the first `bars` bars from `from`) instead of a neutral phrase."},
        "from": {"type": "number", "default": 0, "description": "Seconds into the song where the track's notes are taken from."},
        "bars": {"type": "integer", "default": audition.BARS, "description": "How many bars of the track's notes to play."}}})
    def render_audition(ctx, args):
        """Render a short audition of a sound without changing the song: the entry plays the track's own notes (or a neutral phrase, a one-bar kit pattern, or the file / designed sound as itself, up to 6 s) through the same engine as render_mix. Returns the WAV path; the same audition again comes from the cache."""
        track, entry = args.get("track"), args.get("entry")
        doc = ctx.document(args.get("item")) if track or not entry else None
        if not entry:
            if not track:
                raise RostrumError(codes.BAD_ARGUMENT, "render_audition", "entry", "is needed (or a `track` to hear its own sound)")
            t = next((x for x in doc.data.get("tracks", []) if x["id"] == track), None)
            if t is None:
                raise RostrumError.not_found("render_audition", "track", track, [x["id"] for x in doc.data.get("tracks", [])])
            entry = {k: v for k, v in t.items() if k in ("instrument", *INSTRUMENT_KEYS) and v is not None}
        r = audition.render_audition(ctx.app.state.engine, entry, doc.data if doc else None, track,
                                     float(args.get("from", 0)), int(args.get("bars", audition.BARS)))
        return Reply(f"Audition of {r['what']}: {r['file']}" + (" (from the cache)" if r["cached"] else ""), r, [r["file"]])
