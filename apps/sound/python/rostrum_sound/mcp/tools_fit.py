"""edit_loudness: the exact edit that brings the last render to the master's loudness target (fit_loudness.py)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from rostrum_core import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from rostrum_core.storage import doc_hash

from types import SimpleNamespace

from .. import fit_loudness as fit
from .. import lift_quiet

_PLANS: dict = {}       # (render file, document, track) -> plan: asking, then applying, searches once

ITEM = {"item": {"type": "string", "description": "The Sound document's item id. Optional when only one is open."}}


def register(tools: Tools):
    @tools.tool("edit_loudness", {"properties": {**ITEM,
        "track": {"type": "string", "description": "The track to tame first (`tame_peaks`) or to lower (`trim_track`). Default: the track whose peaks stand highest over its own average (peak / rms) in the last render."},
        "apply": {"enum": ["best", "keep_balance", "tame_peaks", "trim_track", "lift_quiet"], "description": "Apply that option as one change: keep_balance raises the master's `maxLimit` (no track moves); tame_peaks adds (or sets) a gentle compressor on the peaky track(s), first in the chain; trim_track lowers the track; lift_quiet writes the master's volume lane (the quiet parts ridden up); best: the one the reply names best. Without it nothing changes."}}})
    def edit_loudness(ctx, args):
        """Gain staging after a render that landed under the loudness target. Reads the last render and answers the exact edits, measured by the engine, never guessed: `keep_balance` (the
        `maxLimit` that reaches the target, the balance untouched), `tame_peaks` (a gentle compressor (ratio 4:1, attack 5 ms, release 120 ms; a track's own compressor is set instead) first on the most peaked
        track, or the two or three most peaked when one is not enough: the threshold found by re-rendering, the makeup measured so each track keeps its loudness against the mix; reaches the target within
        the master's own `maxLimit`, balance as written) and `trim_track` (the smallest volume cut (at most 12 dB) of the most peaked track that reaches the target within `maxLimit`; the balance moves).
        When the target needs more than ~3 dB of limiting, also `lift_quiet`: ride the quiet parts up instead of squashing the loud ones (music with real dynamics: a soft intro, a crescendo, a climax). It writes the master's volume lane from the last render's short-term loudness: every moment more than 6 dB under the loudest rises by half that distance, at most 4 dB, slowly (1.5 dB a second at most), near-silence (fades, the ring-out) never lifted on its own; loud and soft keep their order, so a crescendo stays a crescendo. Measured before it is offered: it says the limiting the target needs after it (need_after) against now (need_before). Apply it, render, then keep_balance usually needs much less. The lane stays editable (inspect it, change it with automation.set).
        `best`: keep_balance when it raises `maxLimit` by at most 1 dB and the limiting stays within ~3 dB, else tame_peaks (the master stays transparent), else whatever is possible. Each option says how much limiting it leaves on the master: over ~3 dB starts to flatten acoustic drums and piano, so for acoustic music tame_peaks is usually the better way to a streaming target. Each option has `ops`, ready for edit_document; `apply` makes one as a single change. A target that cannot be reached is said, never faked (tame_peaks tries the most it may do first and says at once when even that is not enough); an option that can't be worked out on this song says why and leaves the others (`apply: keep_balance` needs no search renders and answers at once); `apply` of an option that is not possible fails the job and changes nothing.
        Example: {"apply": "best"}. Returns a job with or without `apply` (it renders to search; about 15 s for a one-minute song of six to ten tracks, longer on a busy machine or a long song): read it with inspect_job wait_s."""
        doc = ctx.document(args.get("item"))
        state = ctx.app.state
        r = state.last_render(doc.item_id, "edit_loudness")

        def work(job):
            job.progress(note="measuring")
            root = doc.data
            master = (root.get("master") or [{}])[0]
            only = "keep_balance" if args.get("apply") == "keep_balance" else None
            full = (r.get("file"), doc_hash(root), args.get("track"))
            key = full if full in _PLANS or not only else (only, *full)     # a whole plan answers keep_balance too
            if key not in _PLANS:
                with tempfile.TemporaryDirectory(prefix="fit_", dir=state.renders(doc.item_id)) as tmp:
                    _PLANS.clear()
                    _PLANS[key] = p = fit.plan(r, master, {t["id"]: t for t in root.get("tracks", [])}, root, state.engine, Path(tmp), args.get("track"), only)
                    if not only and p.get("options") and lift_quiet.worth_it(p["need_db"]) and r.get("file"):
                        p["options"].append(fit._alone("lift_quiet", lambda: {"name": "lift_quiet", **lift_quiet.plan(
                            SimpleNamespace(data=root, folder=doc.folder), r, state.engine, Path(tmp))}))
            p = _PLANS[key]
            words, applied = p["words"] + "".join(f" [{o['name']}] {o['words']}" for o in p["options"]), None
            ask = p.get("best") if args.get("apply") == "best" else args.get("apply")
            if p.get("best"):
                words += f" Best: {p['best']}."
            if args.get("apply"):
                pick = next((o for o in p["options"] if o["name"] == ask), None)
                if not pick or not pick.get("ops"):     # asked for and impossible: a failure, never a quiet "nothing"
                    raise RostrumError(codes.CHECK_FAILED, "edit_loudness", f'"apply": "{args["apply"]}"', "is not possible here, nothing was changed: "
                                       + (pick["words"] if pick else "no such option"), hint=words)
                else:
                    doc.apply(pick["ops"], ctx.who, label=f"Fit loudness ({ask})")
                    applied, words = ask, words + f" Applied {ask}: render again to check."
            elif p.get("best"):
                words += " Apply it with edit_loudness " + json.dumps({"apply": p["best"]}) + " (or another by name), or give its ops to edit_document."
            return Reply(words, {**p, "applied": applied})

        return ctx.job(f"edit_loudness {doc.item_id}", work)
