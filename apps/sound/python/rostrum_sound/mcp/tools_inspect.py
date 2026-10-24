"""Sound's own inspect tools: what the engine accepts, what an instrument can play, what sounds are installed, and the
user's own sound folders (indexed once, searched by kind and shape: userlib)."""
from __future__ import annotations

from rostrum_core import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from .. import library, roles, userlib
from ..userlib.kinds import OFFERED


FORMS = ("builtIn", "model", "synth", "sfz", "kit", "kitSfz")


def _instrument(args) -> dict:
    forms = [k for k in FORMS if args.get(k)]
    if len(forms) != 1:
        raise RostrumError(codes.BAD_ARGUMENT, "inspect_instrument", "the instrument", f"needs exactly one of {', '.join(FORMS)}",
                           list(FORMS))
    return {forms[0]: args[forms[0]]}


def register(tools: Tools):
    @tools.tool("inspect_engine", {"properties": {}})
    def inspect_engine(ctx, args):
        """Every name the sound engine accepts: tones, reverb spaces, EQ shapes, built-in instruments, drum names, effects with their fields and defaults; and which built-in sound suits which part (comp, bass, lead, pad, groove), where it sounds best and what it sounds like (`roles`)."""
        d = ctx.app.state.engine.request("describe")
        said = "; ".join(r["line"] for r in roles.rows())
        return Reply(f"Engine {d['engine']}, contract {d['contract']}: {len(d['builtIns'])} built-in instruments, "
                     f"{len(d['effects'])} effect types, {len(d['spaces'])} reverb spaces. Which sound for which part: {said}.",
                     {**d, "roles": roles.rows()})

    @tools.tool("inspect_instrument", {"properties": {
        "builtIn": {"type": "string"}, "model": {"type": "string"}, "synth": {"type": "string"},
        "sfz": {"type": "string", "description": "Absolute path to an .sfz file."},
        "kit": {"type": "string", "enum": ["synth"]}, "kitSfz": {"type": "string"}}})
    def inspect_instrument(ctx, args):
        """What an instrument can play before you write for it: its lowest and highest note, gaps, velocity layers, or a kit's drum names; for a built-in sound also which part it suits and where it sounds best (`role`)."""
        inst = _instrument(args)
        r = ctx.app.state.engine.request("range", instrument=inst)
        k = roles.key(inst)
        said = f" {roles.line(k)}." if k in roles.ROLES else ""
        if k in roles.ROLES:
            r = {**r, "role": roles.ROLES[k]._asdict()}
        if r.get("low") and said:
            return Reply(f"Synthesized: plays any key.{said}", r)
        if r.get("low"):
            gaps = f", {len(r['gaps'])} gaps" if r.get("gaps") else ""
            return Reply(f"Plays {r['low']}–{r['high']}{gaps}, {r.get('layers', 1)} velocity layers.{said}", r)
        return Reply(f"Drums: {', '.join(r['drums'])}.{said}", r)

    @tools.tool("inspect_diagnose", {"properties": {"item": {"type": "string", "description": "The Sound document's item id. Optional when only one is open."}}})
    def inspect_diagnose(ctx, args):
        """Everything wrong with a song, each with the item, what is wrong in words and how to fix it: missing-file (a clip's file is not there; names the clip and the file), outside-project (a clip's file is kept outside the song's folder, so it will not travel with it), pending-take (a clip needs a cleaned take that is not made yet: render_cleanup), broken-tie (a held note that ends before it starts), after-the-end (parts that start after the song's length), no-longer-made (a designed sound an older song still holds). The same list as the Problems chip. Read-only; an empty list means nothing found (it does not judge how the song sounds: look_* and the ears tools do that)."""
        from ..diagnose import problems, said
        doc = ctx.document(args.get("item"))
        found = problems(doc)
        words = said(found) or "nothing wrong found"
        return Reply(f"{doc.item_id}: {len(found)} problem(s). {words}", {"problems": found})

    @tools.tool("inspect_library", {"properties": {
        "find": {"type": "string", "description": "Words that must appear in the path or the description (case-insensitive), e.g. \"cello\" or \"door slam\"."},
        "kind": {"type": "string", "enum": ["instruments", "recordings", "sounds", *OFFERED], "default": "instruments",
                 "description": "instruments / recordings: the installed packs. sounds (all) or a sound kind (foley, ambience, a struck hit, …): "
                                "the user's own sound folders, cut into single sounds and measured."},
        "folder": {"type": "string", "description": "Absolute path to one of the user's sound folders (a Sonniss bundle, BOOM, "
                   "Soundly exports, their recordings): listed in their settings and indexed once (later calls read the index)."},
        "length": {"type": "string", "enum": ["short", "medium", "long"], "description": "short < 0.5 s, medium < 1.5 s, long."},
        "brightness": {"type": "string", "enum": ["dark", "mid", "bright"]},
        "attack": {"type": "string", "enum": ["sharp", "medium", "soft"], "description": "sharp < 15 ms to its peak, soft > 60 ms."},
        "seconds": RANGE, "attack_ms": RANGE, "lufs": RANGE,
        "brightness_range": {**RANGE, "description": "[low, high] on 0 (250 Hz) … 1 (8 kHz)."},
        "limit": {"type": "integer", "default": 40, "minimum": 1, "maximum": 400}}})
    def inspect_library(ctx, args):
        """Sounds to use. Installed packs under <assets>/sounds, settings.assets_dir (kind instruments / recordings): each with its path, what
        it is, its category and length. The user's own sound folders (kind sounds or a sound kind; `folder` adds one): every
        file cut into single sounds, each with its file, start and end in it (use as a clip's in_ / length), kinds, length,
        attack, loudest moment (peak_s), brightness and loudness; filter by words, plain shape words or [low, high] ranges.
        Nothing is copied from the user's folders. Guide: inspect_guide 'library'."""
        kind, words = args.get("kind", "instruments"), args.get("find") or ""
        added = _add_folder(args["folder"]) if args.get("folder") else None
        if kind in ("instruments", "recordings") and not added:
            return _installed(kind, words, args.get("limit", 40))
        return _user_sounds(None if kind in ("sounds", "instruments", "recordings") else kind, words, args, added)


RANGE = {"type": "array", "items": {"type": ["number", "null"]}, "minItems": 2, "maxItems": 2,
         "description": "[low, high]; either may be null."}


def _installed(kind, words, limit):
    try:
        found = library.find(kind, words)
    except FileNotFoundError as e:
        raise RostrumError(codes.NOT_FOUND, "inspect_library", str(library.LIBRARY), "is not installed") from e
    shown = f", showing the first {limit} (raise limit or narrow find)" if len(found) > limit else ""
    sounds = [library.describe(p) for p in found[:limit]]
    sampled = (" These are sampled (SFZ) instruments: their level is the file's, and inspect_instrument sfz=<path> gives each "
               "one's range. The built-in sounds (no file, level-matched) and which part each suits: inspect_engine."
               if kind == "instruments" else "")
    return Reply(f"{len(found)} {kind} found" + (f" for \"{words}\"" if words else "") + f" under {library.LIBRARY}{shown}.{sampled}",
                 {"sounds": sounds, "total": len(found), "more": len(found) > limit})


def _add_folder(folder) -> dict:
    r = userlib.add_folder(folder)
    return {k: r[k] for k in ("folder", "files", "from_cache", "files_from_cache", "took_s", "skipped")} | {"sounds": len(r["sounds"])}


def _user_sounds(kind, words, args, added):
    if not userlib.list_folders():
        raise RostrumError(codes.NOT_FOUND, "inspect_library", "your sound folders", "are not set up yet",
                           hint="Pass folder=<absolute path of a sound folder> to add and index one.")
    r = userlib.search(kind=kind, words=words, length=args.get("length"), brightness=args.get("brightness"),
                       attack=args.get("attack"), seconds=args.get("seconds"), brightness_range=args.get("brightness_range"),
                       attack_ms=args.get("attack_ms"), lufs=args.get("lufs"), limit=args.get("limit", 40))
    sounds = [{k: v for k, v in s.items() if k not in ("folder_words", "ucs") or v} for s in r["sounds"]]
    head = ""
    if added:
        head = (f"Indexed {added['folder']}: {added['files']} files, {added['sounds']} sounds"
                f"{' (from the index, unchanged)' if added['from_cache'] else ''} in {added['took_s']} s"
                + (f"; {len(added['skipped'])} files could not be read (see skipped)" if added["skipped"] else "") + ". ")
    asked = " ".join(x for x in (args.get("length"), args.get("brightness"), args.get("attack"), kind or "sounds") if x)
    more = " (raise limit or narrow the search)" if r["more"] else ""
    return Reply(f"{head}{r['total']} {asked} found" + (f" for \"{words}\"" if words else "") + f" in your sound folders{more}.",
                 {"sounds": sounds, "total": r["total"], "more": r["more"], "folders": userlib.list_folders(),
                  **({"indexed": added} if added else {})})
