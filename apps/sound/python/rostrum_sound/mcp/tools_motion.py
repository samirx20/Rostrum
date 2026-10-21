"""edit_sounds_from_motion: designed sounds placed from the picture's motion (data the 2D app hands over, read-only).
Every sound is a `sound` item made through the script merge, so running it again after the picture changes moves the
sounds with it and keeps what a person changed."""
from __future__ import annotations

import json
from pathlib import Path

from rostrum_core import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from ..motion import read, score
from ..script import run_source


def register(tools: Tools):
    @tools.tool("edit_sounds_from_motion", {"required": ["samples"], "properties": {
        "item": {"type": "string", "description": "The Sound document's item id. Optional when only one is open."},
        "samples": {"type": "string", "description": "Absolute path to the motion samples JSON (per layer x, y, scale, "
                    "opacity at `rate` per second; see inspect_guide 'designed-sounds')."},
        "glue": {"type": "boolean", "default": True, "description": "Route the UI tracks into the ui bus (short "
                 "room + light compressor), made if missing."}}})
    def edit_sounds_from_motion(ctx, args):
        """Read the motion events (moves with their speed curves, landings, snaps, presses, steps) and place a designed
        sound on each: a whoosh shaped by the move's own speed and pan, a click where it lands hard, a press and release,
        a tick per step. A starting point: change any sound with sound.set; re-running keeps those changes. Answers the
        events with their times and the sounds made."""
        p = Path(args["samples"])
        if not p.is_file():
            raise RostrumError(codes.NOT_FOUND, "edit_sounds_from_motion", f'samples "{p}"', "is not a file")
        samples = json.loads(p.read_text(encoding="utf-8"))
        doc = ctx.document(args.get("item"))
        evs = read.events(samples)
        source, tracks = score.script(evs, samples["width"], samples["height"])
        report = ctx.run_script(doc, "sounds-from-motion.py", run_source(source, "sounds-from-motion.py"))
        if args.get("glue", True):
            ops = score.glue_ops(doc.data, tracks)
            if ops:
                ctx.apply(doc, ops, label="UI glue bus")
        kinds = {k: sum(1 for e in evs if e["kind"] == k) for k in ("move", "snap", "press", "step")}
        held = [h["key"] for h in report.held]
        text = (f"{len(evs)} motion events ({', '.join(f'{n} {k}' for k, n in kinds.items() if n)}) -> sounds on "
                f"{', '.join(tracks)}." + (f" Kept a person's changes: {', '.join(held)}." if held else ""))
        return Reply(text, {"events": [{k: v for k, v in e.items() if k not in ("speed", "x")} for e in evs],
                            "tracks": tracks, "held": held})
