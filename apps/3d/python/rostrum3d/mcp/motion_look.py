"""look_motion: what moves in a shot and how, read from the document as the scene compiler resolves it (no rendering):
per item its path in the world and on the picture, its speed per frame, stops and sudden jumps; and the findings:
leaving the picture, two shapes passing through each other. 2D's look_motion is the model; the arithmetic is shared
(rostrum_core.motion)."""
from __future__ import annotations

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools
from rostrum_core.motion.report import LIMIT, capped, examples, stem

from ..faults import shot_faults
from ..motion_track import Track
from ..sim import fall_view
from ..sim.cut_note import cut_lines
from . import motion_found as M, motion_sim
from .shot import ITEM_SHOT, check_frame, doc_and_shot

tools = Tools()
OVERLAP_TEST = ("oriented boxes: each shape's own box turned and scaled with it (a ball: an upright box round it, however it rolls; a clay: the box its pieces reach), so a hollow "
                "shape such as an open case counts as full")
_ORDER = {"passes_through": 0, "jumps": 1, "leaves_frame": 2}
_ASK = "ask with `all: true`, a bigger `limit`, or `items` for the ones you are tuning."


def _range(ctx, info: dict, args: dict) -> range:
    a, b = args.get("frames", [info["start"], info["end"]])
    check_frame(ctx, info, a)
    check_frame(ctx, info, b)
    if b <= a:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"frames [{a}, {b}]", "hold fewer than two frames, so nothing can move in them",
                           hint="Give the first and the last frame, the last after the first.")
    return range(a, b + 1)


def _pick(ctx, track: Track, asked: list[str] | None) -> list[str]:
    known = track.ids()
    for i in asked or ():
        if i not in known:
            raise RostrumError.not_found(ctx.tool, "item", i, known, "the items this shot draws")
    return list(asked) if asked else known


def _line(f: dict) -> str:
    p = f["path"]
    a, b = f["moving"][0][0], f["moving"][-1][1]
    out = (f'{f["id"]}: moves frames {a}–{b}; path {p["length_m"]:g} m, {p["from"]} → {p["to"]} m'
           f'{"; on the picture " + str(p["screen_from"]) + " → " + str(p["screen_to"]) + " px" if p["screen_from"] and p["screen_to"] else ""}'
           f'; peak {f["peak"]["m_s"]:g} m/s at frame {f["peak"]["frame"]}.')
    out += "".join(f' Stops frames {s["frames"][0]}–{s["frames"][1]} ({s["seconds"]:g} s).' for s in f["stops"])
    return out


def _who(x: dict) -> list[str]:
    return x.get("items") or [x["item"]]


def grouped(found: list[dict]) -> list[dict]:
    """Identical findings (copies made in a loop: mote_1 … mote_40 each passing through the ground) one line with a count."""
    groups: dict[tuple, list[dict]] = {}
    for x in found:
        groups.setdefault((x["kind"], x.get("how"), tuple(stem(i) for i in _who(x))), []).append(x)
    out = []
    for (kind, how, _), members in groups.items():
        if len(members) == 1:
            out.append(members[0])
            continue
        ids = sorted({i for m in members for i in _who(m)})
        what = {"passes_through": "overlap (pass through each other)", "jumps": "jump", "leaves_frame": f"are {how} outside the picture"}[kind]
        out.append({"kind": kind, "count": len(members), "items": ids[:10],
                    "text": f"{len(members)} findings: {examples(ids)} {what}, frames {min(m['frames'][0] for m in members)}–"
                            f"{max(m['frames'][1] for m in members)} (ask `items` for each one's frames)."})
    return sorted(out, key=lambda g: (_ORDER[g["kind"]], -g.get("count", 1), g.get("frames", [0])[0]))


@tools.tool("look_motion", {"properties": {**ITEM_SHOT,
    "frames": {"type": "array", "items": {"type": "integer", "minimum": 0}, "minItems": 2, "maxItems": 2,
               "description": "[first, last] frame to measure (the shot's own numbering). Default: the whole shot."},
    "items": {"type": "array", "items": {"type": "string"}, "description": "Only these items (all of them listed, no limit); "
              "passing through is still checked against every shape in the shot."},
    "full": {"type": "boolean", "description": "Adds each item's speed per frame (m/s, and px/s on the picture), its jumps and "
                                               "its moving stretches to the data. Default false: a line per moving item."},
    "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": LIMIT, "description": "Without `items`: how many "
              "moving items and finding lines to list (default 20); the reply says how many more there are."},
    "all": {"type": "boolean", "description": "Every moving item and every finding line, no cap."}}})
def look_motion(ctx, args):
    """What moves in a shot and how, measured on every frame from the document's evaluated animation (keys, stepped timing,
    aims, sticks, follows, poses, mirrored copies, exactly as the scene compiler resolves them); nothing is rendered. Per
    moving item: when it moves, its path (its pivot's world place, first → last, length in metres, and where it is seen on
    the shot camera's picture in px), its peak speed and the frame of it, and its stops (still stretches between moves,
    at least 0.25 s). Findings, facts only, no scores: two shapes passing through each other (both named, the frame span
    and how deep), sudden jumps (a step at least 1 cm and 4× bigger than the frames either side: a teleport or a snap),
    and an item partly or wholly outside the picture (frame spans; only when that changes: it leaves or comes in). Overlap test: each shape's own box turned and scaled
    with it (oriented boxes; a ball: an upright box round it; a clay: the box its pieces reach), so a hollow shape counts as full; touching (under 0.5 mm)
    is not overlap. Hidden items are left out. Short by default: a line a moving item, identical findings one line,
    passing through first; `items` for just those, `full` for the speed per frame, `frames` for part of the shot.
    Simulated things: one set to Falls is measured where the shot's stored simulation has it (as the viewport shows it),
    and checked for passing through like any shape; when the simulation is out of date (the older result is measured)
    or not computed (they are where their keys put them) the reply says so first and gives no all-clear: run_simulation,
    wait with inspect_job, then look again. A cloth's folds and each copy of a falling copies item are not measured here
    (named under not measured). For every falling thing and cloth of the stored result (copies and cloth included) an
    "On screen" line says over which frames it drops (until it first lands) and how far, how many of those frames the
    shot camera's picture shows it in and how many it drops outside (above, below, beside), when it enters and lands, or that it starts already at rest (a copies item: judged copy by copy, how many fall, over which frames they start, the median drop and time seen), with the fix
    when the fall isn't seen well (sim.start_in_view, fallStart); data `fallsOnScreen`. "Fault:" lines (not with `items`): a part that separates from the figure it was joined to, a thing floating above what is under it while holding its height (cm), a subject cut by the frame edge or leaving it (which edge, from when); data `faults`. Fails with the reason on an unknown item, fewer than two frames, or nothing moving."""
    doc, info = doc_and_shot(ctx, args)
    frames = _range(ctx, info, args)
    sim = motion_sim.moves(doc.data, info, ctx.app.folder)
    track = Track(doc.data, info, frames, ctx.app.folder, sim)
    ids = _pick(ctx, track, args.get("items"))
    every = track.ids()
    rows = {i: track.rows(i) for i in every}
    known = {i: M.item_facts(i, rows[i], info) for i in every}
    facts = [known[i] for i in ids]
    turning = {i for i in every if any(x["solid"] != rows[i][0]["solid"] for x in rows[i])}
    moving = {i for i in every if known[i]["moves"]} | turning
    falls = [r for r in fall_view.views(doc.data, info, ctx.app.folder) if not args.get("items") or r["item"] in ids] if sim else []
    faults = [] if args.get("items") else shot_faults(doc.data, info["id"], ctx.app.folder, (frames[0], frames[-1]), track=track)
    if not moving & set(ids) and not any(r.get("moving") for r in falls):   # copies falling in a simulation count as motion
        unseen = f' ({"; ".join(sim["skip"].values())})' if sim and sim["skip"] else ""
        raise RostrumError(codes.NOT_FOUND, ctx.tool, f"frames {frames[0]}–{frames[-1]}", ("nothing measured moves in them" if sim else "nothing moves in them") +
                           (f' among {", ".join(ids)}' if args.get("items") else "") + unseen + (f'. {sim["line"]}' if sim and sim["line"] else "") +
                           "".join(f" {r['line']}" for r in falls) + "".join(f" Fault: {x}" for x in faults),
                           hint="Check the keys with inspect_animations, or measure other frames.")
    found = [*M.passing_through(rows, moving, info), *M.jump_findings(facts, info),
             *[x for i in ids for x in M.leaving(i, rows[i], info)]]
    if args.get("items"):
        found = [x for x in found if set(_who(x)) & set(ids)]
    groups = grouped(found)
    cap = None if args.get("all") or args.get("items") else int(args.get("limit", LIMIT))
    movers = [f for f in facts if f["moves"]]
    notes = []
    if cap is not None and len(movers) > cap:
        notes.append(f"{len(movers) - cap} more moving items not listed: ask with `items`, `all: true` or a bigger `limit`.")
        movers = movers[:cap]
    if cap is not None:
        groups, rest = capped(groups, cap, _ASK)
        notes += [rest] if rest else []
    still = [f["id"] for f in facts if not f["moves"] and not (sim and f["id"] in sim["skip"])]
    turn_only = sorted(set(still) & turning)
    head = (f'Measured frames {frames[0]}–{frames[-1]} of shot "{info["id"]}" ({len(frames)} frames at {info["fps"]:g} fps), '
            f'{len(ids)} items, {len(moving & set(ids))} moving; renderer: none (read from the document). '
            f'Overlap test: {OVERLAP_TEST}.')
    warn = sim["line"] if sim and sim["state"] != "stored" else None
    lines = ([sim["line"]] if sim and sim["line"] else []) + [_line(f) for f in movers]
    lines += [f"On screen: {r['line']}" for r in falls] + [f"On screen: {x}" for x in cut_lines(falls, frames[0], frames[-1], info["start"], info["fps"])]
    if still:
        lines.append(f'{len(still)} not travelling: {examples(still, 10)}' + (f' ({", ".join(turn_only)} turn or change size in place)' if turn_only else "") + ".")
    lines += [f"Fault: {x}" for x in faults]
    if track.skipped:
        lines.append("Not measured for overlap or the picture (no shape known here): " + "; ".join(track.skipped.values()) + ".")
    lines += [g["text"] for g in groups] or [
        "No findings in what was measured, but the simulation is not up to date (see above): this is not an all-clear."
        if warn else "No findings: nothing passes through anything, jumps, or leaves the picture." if not faults else
        "No overlap, jump or leaving finding (see the faults above)."]
    keep = ("id", "moves", "frames", "path", "moving", "peak", "stops") + (("jumps", "speed_m_s", "screen_speed_px_s") if args.get("full") else ())
    data = {"shot": info["id"], "frames": [frames[0], frames[-1]], "fps": info["fps"], "renderer": None, "overlap_test": "oriented boxes",
            "items": [{k: f[k] for k in keep if k in f} for f in facts if f["moves"] or args.get("full")], "findings": groups,
            "not_measured": track.skipped, "faults": faults, "simulation": sim["state"] if sim else None,
            "fallsOnScreen": [{k: r[k] for k in ("item", "kind", "moving", "drop", "movingFrames", "onScreen", "offScreen", "enters", "lands",
                                                  "where", "startsAtRest", "fix")} for r in falls]}
    return Reply("\n".join([head, *lines, *notes]), data)
