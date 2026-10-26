"""edit_loudness: the exact edit that brings the last render to the master's loudness target (fit_loudness.py)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from rostrum_core import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from .. import fit_loudness as fit

ITEM = {"item": {"type": "string", "description": "The Sound document's item id. Optional when only one is open."}}


def register(tools: Tools):
    @tools.tool("edit_loudness", {"properties": {**ITEM,
        "track": {"type": "string", "description": "The track to lower in the `trim_track` option. Default: the track whose peaks stand highest over its own average (peak / rms) in the last render."},
        "apply": {"enum": ["keep_balance", "trim_track"], "description": "Apply that option as one change: keep_balance raises the master's `maxLimit` (no track moves); trim_track lowers the track. Without it nothing changes."}}})
    def edit_loudness(ctx, args):
        """Gain staging after a render that landed under the loudness target. Reads the last render and answers the exact edits, measured by the engine, never guessed: `keep_balance` (the
        `maxLimit` that reaches the target, the balance untouched) and `trim_track` (the smallest volume cut (at most 12 dB) of the most peaked track, found by re-rendering, that reaches the target within the
        master's own `maxLimit`; the balance moves). Each option has `ops`, ready for edit_document; `apply` makes one as a single change. A target that cannot be reached is said, never faked; `apply` of an option that is not possible fails the job and changes nothing.
        Example: {"apply": "keep_balance"}. Returns a job (it renders to search)."""
        doc = ctx.document(args.get("item"))
        state = ctx.app.state
        r = state.last_render(doc.item_id, "edit_loudness")

        def work(job):
            job.progress(note="measuring")
            root = doc.data
            master = (root.get("master") or [{}])[0]
            with tempfile.TemporaryDirectory(prefix="fit_", dir=state.renders(doc.item_id)) as tmp:
                p = fit.plan(r, master, {t["id"]: t for t in root.get("tracks", [])}, root, state.engine, Path(tmp), args.get("track"))
            words, applied = p["words"] + "".join(f" [{o['name']}] {o['words']}" for o in p["options"]), None
            if args.get("apply"):
                pick = next((o for o in p["options"] if o["name"] == args["apply"]), None)
                if not pick or not pick.get("ops"):     # asked for and impossible: a failure, never a quiet "nothing"
                    raise RostrumError(codes.CHECK_FAILED, "edit_loudness", f'"apply": "{args["apply"]}"', "is not possible here, nothing was changed: "
                                       + (pick["words"] if pick else "no such option"), hint=words)
                else:
                    doc.apply(pick["ops"], ctx.who, label=f"Fit loudness ({args['apply']})")
                    applied, words = args["apply"], words + f" Applied {args['apply']}: render again to check."
            elif any(o.get("ops") for o in p["options"]):
                words += " Apply one with edit_loudness " + json.dumps({"apply": next(o["name"] for o in p["options"] if o.get("ops"))}) + ", or give its ops to edit_document."
            return Reply(words, {**p, "applied": applied})

        return ctx.job(f"edit_loudness {doc.item_id}", work)
