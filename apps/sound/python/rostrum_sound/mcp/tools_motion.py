"""edit_sounds_from_motion: musical answers to the picture's motion (data the 2D app hands over, read-only). It adds
nothing by itself (PURPOSE.md): it lists the moments that could earn a sound and what could answer each (a note or a
hit, a rise from strings / cymbal / piano, or a real recording from the person's library); only the answers asked
for in `add` are written, through the script merge, so running it again after the picture changes moves them and
keeps what a person changed."""
from __future__ import annotations

import json
from pathlib import Path

from rostrum_core import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from .. import userlib
from ..motion import read, score
from ..script import run_source

FORMAT = "rostrum.motion-samples/1"      # the 2D app's motion samples (apps/2d/MOTION.md › Motion samples)


def register(tools: Tools):
    @tools.tool("edit_sounds_from_motion", {"required": ["samples"], "properties": {
        "item": {"type": "string", "description": "The Sound document's item id. Optional when only one is open."},
        "samples": {"type": "string", "description": "Absolute path to the motion samples JSON from Rostrum2D render_export format=motion (per layer x, y, scale, "
                    "opacity at `rate` per second; see inspect_guide 'scoring-to-picture')."},
        "add": {"type": "array", "items": {"type": "string"}, "default": [], "description":
                'The answers to write, each "<moment id>:<answer>" from the suggestions (e.g. "land1:strings", '
                '"snap2:note", "press3:library"). Empty: nothing is added, only the suggestions come back.'},
        "key": {"type": "string", "default": "C major", "description": 'The key the notes are in ("D minor", "Bb major").'},
        "glue": {"type": "boolean", "default": True, "description": "Route library-recording tracks into the ui bus "
                 "(short room + light compressor), made if missing."},
        "detail": {"type": "boolean", "default": False, "description": "List every removed item in the reply's data (else counts and the first few)."}}})
    def edit_sounds_from_motion(ctx, args):
        """Read the motion (moves and where they land, snaps, presses, steps) and suggest musical answers for the
        moments that could earn a sound: a struck note or a hit on a landing, a rise into it from strings, a cymbal
        roll or a piano run, a real recorded click from the person's library for a press. Adds nothing unless asked:
        pass `add` with the chosen "<id>:<answer>" pairs. Silence is an answer; most moves need none."""
        p = Path(args["samples"])
        if not p.is_file():
            raise RostrumError(codes.NOT_FOUND, "edit_sounds_from_motion", f'samples "{p}"', "is not a file")
        samples = json.loads(p.read_text(encoding="utf-8"))
        missing = [k for k in ("rate", "width", "height", "layers") if k not in samples]
        if missing or samples.get("format", FORMAT) != FORMAT:
            raise RostrumError(codes.BAD_ARGUMENT, "edit_sounds_from_motion", f'samples "{p}"',
                               f'is not a {FORMAT} file' + (f' (no {", ".join(missing)})' if missing else ""),
                               hint='Write one with Rostrum2D: render_export format="motion" (or Export › Motion samples).')
        rows = score.suggest(read.events(samples))
        shown = [{k: v for k, v in r.items() if k != "event"} | {"says": {a: score.SAYS[a] for a in r["answers"]}} for r in rows]
        by_id, chosen = {r["id"]: r for r in rows}, []
        for pick in args.get("add", []):
            sid, _, answer = pick.partition(":")
            if sid not in by_id or answer not in by_id[sid]["answers"]:
                raise RostrumError(codes.BAD_ARGUMENT, "edit_sounds_from_motion", f'add "{pick}"', "is not one of the suggestions",
                                   hint="Pick from: " + ", ".join(f'{r["id"]}:{a}' for r in rows for a in r["answers"]))
            chosen.append((by_id[sid], answer))
        if not chosen:
            text = (f"{len(rows)} moments could earn a sound; nothing added. Choose with add=[\"<id>:<answer>\"], "
                    "or leave them silent." if rows else "No moment here needs a sound; nothing added.")
            return Reply(text, {"suggestions": shown, "added": []})
        doc = ctx.document(args.get("item"))
        lib = userlib.library() if any(a == "library" for _, a in chosen) else None
        try:
            source, tracks = score.script(chosen, args.get("key", "C major"), samples["width"], lib)
        except ValueError as e:
            raise RostrumError(codes.BAD_ARGUMENT, "edit_sounds_from_motion", f'key "{args.get("key")}"', str(e)) from None
        report = ctx.run_script(doc, "sounds-from-motion.py", run_source(source, "sounds-from-motion.py"))
        if args.get("glue", True):
            ops = score.glue_ops(doc.data, tracks)
            if ops:
                ctx.apply(doc, ops, label="UI glue bus")
        held = [h["key"] for h in report.held]
        said = ", ".join(f"{s['id']}: {score.SAYS[a]}" for s, a in chosen)
        text = (f"Added {said} on {', '.join(tracks)}."
                + (f" Kept a person's changes: {', '.join(held)}." if held else ""))
        return Reply(text, {"suggestions": shown, "added": [f"{s['id']}:{a}" for s, a in chosen], "tracks": tracks,
                            "held": held,
                            "removed": report.removed if args.get("detail") else {"count": len(report.removed), "first": report.removed[:5]}}, warnings=report.warnings())
