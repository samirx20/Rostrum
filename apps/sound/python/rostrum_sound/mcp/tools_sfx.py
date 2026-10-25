"""Effects work against a picture (from P-SFX): eyes on the video, and the cut pool (recordings cut into single
sounds with measured facts, analysed once and cached). Both read files; neither changes the document."""
from __future__ import annotations

from pathlib import Path

from rostrum_core import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from .. import sfx


def _file(path, where) -> str:
    p = Path(path or "")
    if not p.is_file():
        raise RostrumError(codes.NOT_FOUND, where, f'"{path}"', "is not a file")
    return str(p)


def register(tools: Tools):
    @tools.tool("look_video", {"required": ["video", "what"], "properties": {
        "item": {"type": "string"},
        "video": {"type": "string", "description": "Absolute path to the picture the sound is for."},
        "what": {"type": "string", "enum": ["frames", "sheet", "motion"],
                 "description": "frames: a labelled strip around `at`; sheet: a contact sheet; motion: movement and sudden-stop candidates."},
        "at": {"type": "number", "description": "frames: the time to look around (seconds)."},
        "span": {"type": "integer", "default": 2, "description": "frames: how many frames are shown on each side of `at` (a whole number, not seconds)."},
        "every": {"type": "number", "default": 0.5, "description": "sheet: seconds between tiles."},
        "min_confidence": {"type": "number", "default": 0.5, "description": "motion: drop weaker stop candidates (0 … 1)."}}})
    def look_video(ctx, args):
        """See the picture: a frame strip, a contact sheet, or motion with impact candidates. Each picture is labelled with time and frame."""
        video = _file(args["video"], "look_video")
        doc = ctx.document(args.get("item"))
        out = ctx.app.state.look_dir(doc.item_id)
        what = args["what"]
        if what == "frames":
            if "at" not in args:
                raise RostrumError(codes.BAD_ARGUMENT, "look_video", "at", "is needed for frames")
            r = sfx.frames(video, args["at"], span=int(args.get("span", 2)), out_dir=str(out))
            line = f"Frames around {args['at']:.2f} s ({r['fps']:.2f} fps)."
        elif what == "sheet":
            r = sfx.sheet(video, str(out / f"{Path(video).stem}-sheet.png"), every=args.get("every", 0.5))
            line = f"Contact sheet: {r.get('tiles')} tiles."
        else:
            def work(job):
                job.progress(note="reading the video")
                m = sfx.motion(video, str(out), min_confidence=args.get("min_confidence", 0.5))
                return Reply(f"{len(m['candidates'])} sudden-stop candidates, {len(m.get('cuts', []))} picture cuts.", m, [m["png"]], [m["png"]])
            return ctx.long(f"motion {Path(video).name}", work, key=f"motion:{video}:{args.get('min_confidence', 0.5)}")
        return Reply(line, r, [r["png"]], [r["png"]])

    @tools.tool("inspect_cuts", {"required": ["recordings"], "properties": {
        "recordings": {"type": "array", "items": {"type": "string"}, "description": "Absolute paths of recordings to cut."},
        "mode": {"type": "string", "enum": ["hits", "beds"], "default": "hits", "description": "hits: single sounds on their transients; beds: steady stretches."},
        "limit": {"type": "integer", "default": 60, "description": "Cuts listed in the reply (all are cached)."}}})
    def inspect_cuts(ctx, args):
        """The cut pool: recordings cut into single sounds, each with start, end, peak, floor, attack, brightness and low-end share. Analysed once, then read from the cache."""
        paths = [_file(p, f"inspect_library (what: cuts) › recordings[{i}]") for i, p in enumerate(args["recordings"])]

        def work(job):
            job.progress(note=f"cutting {len(paths)} recordings")
            r = sfx.pool(paths, mode=args.get("mode", "hits"))
            cuts = r["cuts"]
            data = {**r, "cuts": cuts[: args.get("limit", 60)], "total": len(cuts)}
            return Reply(f"{len(cuts)} cuts from {len(paths)} recordings ({r.get('from_cache', 0)} read from the cache).", data)
        return ctx.long("cut pool", work, key="cuts:" + "|".join(paths) + args.get("mode", "hits"))
