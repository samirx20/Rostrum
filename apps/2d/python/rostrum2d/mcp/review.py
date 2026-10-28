"""review: the film's weakest moments, ranked, as located faults with times: blank stretches, titles at the frame edge,
faint old headings, parts not drawn in yet, held poses and held framing, subjects cut by the edge, stray specks, layers outside their screen, crowded lock-ups, beats that never
happened. Facts from the document (review_facts) and from small pictures (look_empty), never a taste score. The export
reply ends with the top ones (`after_export`, through session_clock), so the next fix pass has a concrete target."""
from __future__ import annotations

import tempfile
from pathlib import Path

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from . import edge_cut, look_empty, render
from . import review_beats, review_facts as rf, review_room
from .pick import ITEM_COMP, doc_and_comp

tools = Tools()
EVERY = look_empty.EVERY
OPENING = 1.0             # a blank under this long at the very start or end is an opening or closing fade
# The order faults are named in: what a viewer sees as broken first, then what reads as lifeless, then what may be meant.
RANK = {"empty": 100, "text_edge": 90, "ghost_text": 85, "beat_missing": 80, "beat_wrong_time": 78, "set_hidden": 70, "block": 65, "pose_held": 60, "arms_straight": 58, "limbs_thin": 57,
        "speck": 88, "outside": 75, "crowded": 45, "text_margin": 42,
        "framing_held": 55, "still": 50, "rig_cut": 48, "empty_edge": 40, "edge_cut": 30, "small_text_edge": 28, "washed": 25}


def _kind(r: dict, duration: float) -> str:
    k = r["kind"]
    if k == "empty" and r["end"] - r["start"] <= OPENING + 1e-9 and (r["start"] <= 1e-9 or r["end"] >= duration - 1e-9):
        return "empty_edge"
    return k


def _cuts(rows: list[dict]) -> list[dict]:
    """One line per subject cut by the edge (its longest stretch); a text at the edge is named by review_facts (text_edge)."""
    best: dict[str, dict] = {}
    for c in rows:
        if c["type"] != "text" and (c["id"] not in best or c["end"] - c["start"] > best[c["id"]]["end"] - best[c["id"]]["start"]):
            best[c["id"]] = c
    return [{"kind": "rig_cut" if c["type"] == "rig" else "edge_cut", "start": c["start"], "end": c["end"], "id": c["id"],
             "text": _cut_text(c)} for c in best.values()]


def _cut_text(c: dict) -> str:
    span = f'{c["start"]:g}–{c["end"]:g} s'
    if c["type"] == "rig":
        return f'character "{c["id"]}" is cut by the {c["edge"]} edge of the frame {span} ({c["cut_pct"]} % outside)'
    return f'{span}: {c["id"]} ({c["type"]}) cut at the {c["edge"]} edge, {c["cut_pct"]} % of it outside'


def ranked(faults: list[dict], duration: float) -> list[dict]:
    """Most visible first: by kind (RANK), then the longer stretch; each with `rank_kind`."""
    for f in faults:
        f["rank_kind"] = _kind(f, duration)
    return sorted(faults, key=lambda f: (-RANK.get(f["rank_kind"], 0), -(f["end"] - f["start"]), f["start"]))


def doc_faults(doc_data: dict, comp: dict, beats: list[dict] | None, where: str, step: float = EVERY) -> tuple[list[dict], list[str]]:
    """Every fault the document alone shows, and notes for what could not be measured."""
    duration = comp.get("duration", 5.0)
    times = [round(i * step, 4) for i in range(int(duration / step + 1e-9))]
    vectors, notes = rf.pose_vectors(doc_data, comp, times)
    faults = rf.framing(comp, times, step) + rf.poses(vectors, times, step) + rf.layer_facts(comp, times, step)
    cut = {f["id"] for f in faults if f["kind"] in ("text_edge", "small_text_edge")}
    faults += [f for f in review_room.facts(comp, times, step) if f["kind"] != "text_edge" or f["id"] not in cut]   # a cut title is named once
    if beats:
        faults += review_beats.beats(comp, beats, times, vectors, where)
    return faults, notes


def tell(rows: list[dict], limit: int) -> str:
    if not rows:
        return "No weak moment found: no blank, held or cut-off stretch, no faint leftover text, no stray speck, nothing outside its screen or crowding a lock-up, every declared beat happens on time."
    shown = " ".join(f"{i}. {r['text']}." for i, r in enumerate(rows[:limit], 1))
    more = f" ({len(rows) - limit} more in data.)" if len(rows) > limit else ""
    return f"Weakest moments, most visible first: {shown}{more}"


def after_export(doc_data: dict, comp: dict, quiet: list[dict], cuts: list[dict], limit: int = 3, beats: list[dict] | None = None) -> str:
    """The export reply's last part: the top weakest moments from the checks the export already ran plus the document's
    facts and the declared beats (None: never declared, so ask for them), phrased as the next fix pass."""
    faults, _ = doc_faults(doc_data, comp, beats, "review")
    rows = ranked([dict(q) for q in quiet] + _cuts(cuts) + faults, comp.get("duration", 5.0))
    ask = (' No beats declared: give the brief\'s timed beats as `beats` on the next export ([{"at": 24, "to": 28, '
           '"expect": "lamp reveals"}]) and each export checks they come on time.') if beats is None else ""
    if not rows:
        return "Review: no weak moment found (blank, held, cut-off, faint leftovers). Look at the sheet to judge the rest." + ask
    return tell(rows, limit) + " Fix the top one, then export again (look_review re-checks in seconds)." + ask


BEATS = {"type": "array", "items": {"type": "object", "required": ["at", "expect"], "properties": {
    "at": {"type": "number", "minimum": 0}, "to": {"type": "number", "minimum": 0},
    "expect": {"type": "string", "description": " | ".join(review_beats.BEAT_KINDS)}}},
    "description": 'Beats the brief asks for, checked against the document: [{"at": 25, "to": 30, "expect": "camera move"}]. '
                   "A beat that never happens is named, and one at the wrong time (a layer already showing well before its "
                   "'shows', already whole before its 'reveals': more of it showing over at..to; a move or cut only elsewhere)."}


@tools.tool("look_review", {"properties": {**ITEM_COMP,
                                      "video": {"type": "string", "description": "An exported mp4 to read the pictures from (absolute path); faster than drawing. Default: small pictures drawn from the composition now."},
                                      "beats": BEATS,
                                      "limit": {"type": "integer", "minimum": 1, "maximum": 30, "default": 6, "description": "How many weakest moments to name. Default 6."}}})
def look_review(ctx, args):
    """The film's weakest moments, ranked, each a located fault with times: a near-empty stretch; a title touching the frame
    edge; an old heading still faintly showing behind a new one; a set of parts (a chart's bars, a list's rows) not shown while
    the rest of its group is; a plain card opening empty; a character's pose barely changing for 6 s or more; an arm held nearly straight for 4 s or more;
    a character's arms or legs thin next to its body; framing held
    10 s or more (no camera move or cut); a stretch where nothing moves; a subject cut by the edge; a title inside the edge's safe margin;
    a stray small dot that later grows; a layer showing outside the screen it sits in; a lock-up whose parts touch; a washed-out stretch; and
    each declared beat (`beats`, or the ones last given to an export) that never happens or comes at the wrong time. Samples the whole film every 0.5 s in seconds. Facts, not taste: a held
    title or a planned pause may be meant. Use it after every export: fix the top one, export, review again."""
    doc, comp = doc_and_comp(ctx, args)
    limit, beats = args.get("limit", 6), args.get("beats") or []
    faults, notes = doc_faults(doc.data, comp, beats, ctx.tool)       # beats fail loudly here, before any job
    duration = comp.get("duration", 5.0)
    times = [round(i * EVERY, 4) for i in range(int(duration / EVERY + 1e-9))]
    rigs, more = edge_cut.rig_boxes(doc.data, comp, times)
    cuts = _cuts(edge_cut.scan(comp, times, rigs, EVERY))

    def finish(pixels: list[dict]) -> Reply:
        rows = ranked(pixels + cuts + faults, duration)
        return Reply(tell(rows, limit) + (" Fix the top one, then export again." if rows else ""),
                     {"moments": rows, "every": EVERY, "samples": len(times)}, warnings=notes + more)

    if "video" in args:
        mp4 = Path(args["video"])
        if not mp4.is_file():
            raise RostrumError(codes.NOT_FOUND, ctx.tool, f'video "{mp4}"', "is not a file", hint="Give the absolute path of an mp4.")
        return finish(look_empty.scan_video(mp4))
    fps, last = comp.get("fps", 30), (round(duration * comp.get("fps", 30)) - 1) / comp.get("fps", 30)
    picks = [min(t, last) for t in times]
    scene = render.scene_of(doc, comp["id"], (picks[0], picks[-1]), sorted({round(t * fps) for t in picks}))

    def job_fn(job):
        with tempfile.TemporaryDirectory(prefix="rostrum_review_") as tmp:
            items = [(t, Path(tmp) / f"s{i}.png") for i, t in enumerate(picks)]
            render.small_stills(ctx.tool, scene, items, look_empty.SAMPLE_W, job.progress)
            return finish(look_empty.scan_pngs(items, EVERY, duration))

    return ctx.long(f'look_review {comp["id"]}', job_fn)
