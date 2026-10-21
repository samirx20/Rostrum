"""edit_sounds_from_motion: sounds placed from the picture's motion (data the 2D app hands over, read-only), either
designed by the engine or picked from the user's own sound library. Every sound is a `sound` or `clip` item made
through the script merge, so running it again after the picture changes moves the sounds with it and keeps what a
person changed."""
from __future__ import annotations

import json
from pathlib import Path

from rostrum_core import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from .. import userlib
from ..motion import read, score
from ..script import run_source


def register(tools: Tools):
    @tools.tool("edit_sounds_from_motion", {"required": ["samples"], "properties": {
        "item": {"type": "string", "description": "The Sound document's item id. Optional when only one is open."},
        "samples": {"type": "string", "description": "Absolute path to the motion samples JSON (per layer x, y, scale, "
                    "opacity at `rate` per second; see inspect_guide 'designed-sounds')."},
        "glue": {"type": "boolean", "default": True, "description": "Route the UI tracks into the ui bus (short "
                 "room + light compressor), made if missing."},
        "source": {"type": "string", "enum": ["designed", "library"], "default": "designed", "description":
                   "designed: sounds made by the engine. library: recordings from the user's own sound folders "
                   "(inspect_library folder=…), chosen by kind and shape for each event and placed as clips."}}})
    def edit_sounds_from_motion(ctx, args):
        """Read the motion events (moves with their speed curves, landings, snaps, presses, steps) and place a sound on
        each: a whoosh on the move's fastest moment, panned with it, a click where it lands hard, a press and release,
        a tick per step. source="designed" makes them with the engine (shaped by the move's own speed); "library"
        picks recordings from the user's sound folders (inspect_guide 'library'). A starting point: change any sound
        or clip with sound.set / clip.set; re-running keeps those changes. Answers the events with their times and the
        sounds made."""
        p = Path(args["samples"])
        if not p.is_file():
            raise RostrumError(codes.NOT_FOUND, "edit_sounds_from_motion", f'samples "{p}"', "is not a file")
        samples = json.loads(p.read_text(encoding="utf-8"))
        doc = ctx.document(args.get("item"))
        evs = read.events(samples)
        kind = args.get("source", "designed")
        lib = userlib.library() if kind == "library" else None
        source, tracks = score.script(evs, samples["width"], samples["height"], kind, lib)
        report = ctx.run_script(doc, "sounds-from-motion.py", run_source(source, "sounds-from-motion.py"))
        if args.get("glue", True):
            ops = score.glue_ops(doc.data, tracks)
            if ops:
                ctx.apply(doc, ops, label="UI glue bus")
        kinds = {k: sum(1 for e in evs if e["kind"] == k) for k in ("move", "snap", "press", "step")}
        held = [h["key"] for h in report.held]
        text = (f"{len(evs)} motion events ({', '.join(f'{n} {k}' for k, n in kinds.items() if n)}) -> "
                f"{'library recordings' if kind == 'library' else 'designed sounds'} on {', '.join(tracks)}."
                + (f" Kept a person's changes: {', '.join(held)}." if held else ""))
        return Reply(text, {"events": [{k: v for k, v in e.items() if k not in ("speed", "x")} for e in evs],
                            "tracks": tracks, "held": held, "source": kind})
