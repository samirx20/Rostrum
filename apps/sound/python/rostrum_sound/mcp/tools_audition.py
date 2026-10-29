"""render_audition: hear a stretch of the song (any bars, or a marker ± seconds) in about a second without a full
render (hear.py), with its picture and notes on request; or hear a Library entry (an instrument, a drum kit, a sound
file) through the engine, on the track's own notes when one is given. The document is not touched; the WAV is kept by
content."""
from __future__ import annotations

from rostrum_core import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from .. import audition, hear, master_memo
from ..doc import markers
from .range_target import _seconds

ENTRY = {"type": "object", "description": (
    "What to hear. An instrument: {instrument: builtIn|synth|model|sfz|plugin, builtIn|model|sfz|plugin: name, e.g. builtIn: cello}; a drum kit: {instrument: kit, kit: drums|studio|classic} "
    "or {instrument: kitSfz, kitSfz: path}; a sound file: "
    "{media: absolute path, in: seconds, length: seconds}. Omit it (with `track`) to hear the track's own sound.")}
TIME = "seconds (12.5), {\"bar\": 9}, {\"beat\": 32} or a marker (\"#chorus\", \"#chorus-2\", \"#drop+1beats\")"


def _song_stretch(ctx, doc, args) -> Reply:
    """The song from `from` to `to` (or `around` an `at`), as written now."""
    d = doc.data
    with markers.project(getattr(doc, "folder", None)):
        if "at" in args:
            a, b = hear.window(_seconds(d, args["at"], "render_audition › at"), None, float(args.get("around", 2.0)))
        else:
            a = _seconds(d, args.get("from", 0), "render_audition › from")
            b = _seconds(d, args["to"], "render_audition › to") if "to" in args else None
            a, b = hear.window(a, b, None)
    if b <= a or b - a > hear.MOST_S:
        raise RostrumError(codes.BAD_ARGUMENT, "render_audition", f"from {a:.2f} s to {b:.2f} s",
                           f"is not a stretch of 0 to {hear.MOST_S:g} s", hint="For a longer part: render_mix with from / to.")
    solo = list(args.get("solo") or []) + ([args["track"]] if args.get("track") else [])
    r = hear.hear(ctx.app.state.engine, d, a, b, solo=solo or None, mute=args.get("mute"), master=args.get("master", True),
                  song=master_memo.song_of(ctx.app.state.folder, doc.item_id))
    files, images = [r["file"]], []
    said = (f"Heard {r['from_s']:.2f}-{r['to_s']:.2f} s" + (f" (solo {', '.join(solo)})" if solo else "")
            + f": {r.get('lufs', -70):.1f} LUFS, true peak {r.get('truePeak', -120):.1f} dBTP. {r['file']}" + (" (from the cache)" if r["cached"] else "")
            + (" Level: the song's master from before your latest change; the next listen has it measured again." if r.get("mastered") == "earlier" else ""))
    data = {k: v for k, v in r.items() if k != "series"}
    if args.get("look"):
        png = str(ctx.app.state.look_dir(doc.item_id) / "audition.png")
        hear.picture(png, r["file"], r, doc.item_id)
        data["png"], images = png, [png]
        files.append(png)
    if args.get("notes"):
        found = hear.notes(r["file"], d, r)
        data["notes"] = found
        said += "\nNotes: " + ("; ".join(f"{n['at_s']:.2f} s {n['words'] or n['kind']}" for n in found) if found else "none in this stretch.")
    return Reply(said, data, files, images)


def register(tools: Tools):
    @tools.tool("render_audition", {"properties": {
        "item": {"type": "string", "description": "The Sound document's item id. Optional when only one is open."},
        "entry": ENTRY,
        "track": {"type": "string", "description": "A track id. With `entry`: the instrument or kit plays this track's own notes. Without `entry` and without `to` / `at`: the track's own sound on its own notes. With `to` or `at`: that stretch of the song with this track alone."},
        "from": {"description": f"Where the stretch starts: {TIME}. With only `track` (no `to`): seconds where the track's notes are taken from."},
        "to": {"description": f"Where the stretch ends ({TIME}); default 4 s after `from`. At most {hear.MOST_S:g} s long."},
        "at": {"description": f"A moment to hear around ({TIME}); the stretch is `around` seconds each side."},
        "around": {"type": "number", "default": 2.0, "minimum": 0.1, "maximum": hear.MOST_S / 2, "description": "Seconds each side of `at`."},
        "solo": {"type": "array", "items": {"type": "string"}, "description": "Only these track ids are heard in the stretch."},
        "mute": {"type": "array", "items": {"type": "string"}, "description": "These track ids are not heard in the stretch."},
        "master": {"type": "boolean", "default": True, "description": "False: the stretch before the master stage. True: mastered, its loudness target measured on the stretch alone (so a quiet stretch is raised as a whole song would not be)."},
        "look": {"type": "boolean", "default": False, "description": "Also a picture of the stretch: wave, loudness over time, spectrum over time."},
        "notes": {"type": "boolean", "default": False, "description": "Also the listening notes inside the stretch: the song's asked moments (markers named hit, stop, drop, climax ...) measured, a true peak over the ceiling, clipped samples. Notes to read, never a verdict."},
        "bars": {"type": "integer", "default": audition.BARS, "description": "With only `track` or `entry`: how many bars of the track's notes to play."}}})
    def render_audition(ctx, args):
        """Hear any moment in about a second, without a full render: a stretch of the song as written now (`from` / `to`, or `at` ± `around`; `solo` / `mute`), sounding exactly as that stretch of the full render_mix does (the song's own master and level; until the song's first render the first stretch takes a full-song pass), rendered alone (unchanged tracks from the render cache, a changed one only around the stretch) and kept by content, so the same stretch again is instant. `look` adds its picture, `notes` the listening notes inside it. Or try a sound: `entry` plays the track's own notes (or a neutral phrase, a one-bar kit pattern, or a file as itself, up to 6 s) through the same engine as render_mix. Returns the WAV path; nothing in the song changes."""
        track, entry = args.get("track"), args.get("entry")
        stretch = not entry and ("to" in args or "at" in args or not track)
        doc = ctx.document(args.get("item")) if track or not entry else None
        if stretch:
            return _song_stretch(ctx, doc, args)
        if not entry:
            t = next((x for x in doc.data.get("tracks", []) if x["id"] == track), None)
            if t is None:
                raise RostrumError.not_found("render_audition", "track", track, [x["id"] for x in doc.data.get("tracks", [])])
            entry = audition.entry_of(t)
        start = args.get("from", 0)
        if not isinstance(start, (int, float)) or isinstance(start, bool):
            raise RostrumError(codes.BAD_ARGUMENT, "render_audition", f"from {start!r}", "is seconds when only a track is heard",
                               hint="Add `to` (or `at`) to hear that stretch of the song with the track alone.")
        r = audition.render_audition(ctx.app.state.engine, entry, doc.data if doc else None, track,
                                     float(start), int(args.get("bars", audition.BARS)))
        return Reply(f"Audition of {r['what']}: {r['file']}" + (" (from the cache)" if r["cached"] else ""), r, [r["file"]])
