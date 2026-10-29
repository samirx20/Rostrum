"""review: what the checks measure in the film, ranked, each located with times: blank stretches, titles at the frame edge,
faint old headings, parts not drawn in yet, held poses and held framing, subjects cut by the edge, stray specks, layers outside their screen, crowded lock-ups, beats that never
happened, a near-empty frame mid-film, look-alike opening shots, an end picture held too long, a text partly crossed by a layer
in front (a panel's own background too), a text cut by the edge of the screen or box that clips it, texts on texts, a pointer on a label, a tiny end card, a device cut by the frame edge (and why: placed off the
frame, or nibbled by a camera push-in), a character hidden behind the set or standing on a bare one, a layer its layout jumps in one frame. Rows name
the layers and the numbers. Facts from the document (review_facts) and from small pictures (look_empty), never a taste score
and never a verdict: run_script look, render_export and render_video give them as notes only when asked (`notes: true`)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from . import edge_cut, geometry, look_empty, render
from . import review_beats, review_clip, review_cover, review_device, review_facts as rf, review_frame, review_jump, review_layout, review_offscreen, review_padding, review_panels, review_paint_order, review_room, review_spill
from .review_sample import Sampled
from .pick import ITEM_COMP, doc_and_comp

tools = Tools()
EVERY = look_empty.EVERY
CHECKS = (review_frame.facts, review_cover.facts, review_layout.facts, review_clip.facts, review_device.facts, review_spill.facts, review_panels.facts, review_offscreen.facts, review_padding.facts, review_paint_order.facts, review_jump.facts)   # each (Sampled) -> faults: a new check registers here
OPENING = 1.0             # a blank under this long at the very start or end is an opening or closing fade
# The order faults are named in: what a viewer sees as broken first, then what reads as lifeless, then what may be meant.
RANK = {"empty": 100, "text_edge": 90, "ghost_text": 85, "beat_missing": 80, "beat_wrong_time": 78, "set_hidden": 70, "block": 65, "pose_held": 60, "arms_straight": 58, "limbs_thin": 57,
        "speck": 88, "outside": 75, "crowded": 45, "text_margin": 42,
        "text_crossed": 90, "text_clipped": 91, "text_spill": 90, "sparse": 82, "rig_hidden": 72, "end_held": 54, "alike_open": 52, "bare_set": 44,
        "device_cut": 92, "screen_spill": 91, "push_bars": 92, "push_cut": 91, "text_on_text": 89, "panel_overlap": 89, "off_screen": 91, "text_tight": 80, "pointer_on_text": 87, "end_small": 85,
        "framing_held": 55, "still": 50, "rig_cut": 48, "empty_edge": 40, "edge_cut": 30, "painted_over": 86, "layout_jump": 84, "small_text_edge": 28, "washed": 25}


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
             "type": c["type"], "text": _cut_text(c)} for c in best.values()]


def _cut_text(c: dict) -> str:
    span = f'{c["start"]:g}–{c["end"]:g} s'
    if c["type"] == "rig":
        return f'character "{c["id"]}" is cut by the {c["edge"]} edge of the frame {span} ({c["cut_pct"]} % outside)'
    return f'{span}: {c["id"]} ({c["type"]}) cut at the {c["edge"]} edge, {c["cut_pct"]} % of it outside'


def _named_blank(f: dict, blanks: list[dict]) -> bool:
    """A near-empty stretch the pictures already name as blank (its middle inside one): named once."""
    mid = (f["start"] + f["end"]) / 2
    return f["kind"] == "sparse" and any(b["start"] <= mid <= b["end"] for b in blanks)


def info(faults: list[dict]) -> list[dict]:
    """What a check measured but does not call a fault (a deep push-in past a device's edge, screen texts it cuts)."""
    return [f for f in faults if f.get("info")]


def ranked(faults: list[dict], duration: float) -> list[dict]:
    """Most visible first: by kind (RANK), then the longer stretch; each with `rank_kind`. Info rows are left out, and a
    device's plain edge cut when the device check named it (with why)."""
    blanks = [f for f in faults if f["kind"] == "empty"]
    devices = {f["id"] for f in faults if f["kind"] in ("device_cut", "push_cut", "push_bars", "push_in")}
    faults = [f for f in faults if not _named_blank(f, blanks) and not f.get("info")
              and not (f["kind"] == "edge_cut" and f["id"] in devices)]
    for f in faults:
        f["rank_kind"] = _kind(f, duration)
    return sorted(faults, key=lambda f: (-RANK.get(f["rank_kind"], 0), -(f["end"] - f["start"]), f["start"]))


def doc_faults(doc_data: dict, comp: dict, beats: list[dict] | None, where: str, step: float = EVERY) -> tuple[list[dict], list[str]]:
    """Every fault the document alone shows, and notes for what could not be measured."""
    with geometry.memo():               # the checks share one flattened picture per sampled time
        return _doc_faults(doc_data, comp, beats, where, step)


def _doc_faults(doc_data, comp, beats, where, step):
    duration = comp.get("duration", 5.0)
    times = [round(i * step, 4) for i in range(int(duration / step + 1e-9))]
    vectors, notes = rf.pose_vectors(doc_data, comp, times)
    faults = rf.framing(comp, times, step) + rf.poses(vectors, times, step) + rf.layer_facts(comp, times, step)
    cut = {f["id"] for f in faults if f["kind"] in ("text_edge", "small_text_edge")}
    faults += [f for f in review_room.facts(comp, times, step) if f["kind"] != "text_edge" or f["id"] not in cut]   # a cut title is named once
    sampled = Sampled(doc_data, comp, times, step)
    faults += [f for check in CHECKS for f in check(sampled)]
    faults = review_device.quiet_texts(faults, sampled)      # screen texts a camera push-in cuts: named by the device line
    notes = notes + sampled.notes
    if beats:
        faults += review_beats.beats(comp, beats, times, vectors, where)
    return faults, notes


def tell(rows: list[dict], limit: int) -> str:
    if not rows:
        return "No weak moment found: no blank, held or cut-off stretch, no faint leftover text, no stray speck, nothing outside its screen or crowding a lock-up, no text crossed, cut by its screen's edge or on another text, no pointer on a label, no device cut, no tiny end card, no character hidden or on a bare set, no layout jump, every declared beat happens on time."
    picked, more = few(rows, limit)
    shown = " ".join(f"{i}. {r['text']}." for i, r in enumerate(picked, 1))
    return f"Weakest moments, most visible first: {shown}{more and f' ({more})'}"


PER_KIND = 3        # rows of one kind written out in a summary; the rest are counted (all of them stay in the data)


def few(rows: list[dict], limit: int) -> tuple[list[dict], str]:
    """The ranked rows a summary writes out: in rank order, at most PER_KIND of a kind, at most `limit`; and what is left
    as counts per kind ("" when nothing is): "and 412 more text_on_text, 2 more edge_cut in data"."""
    picked, per = [], {}
    for r in rows:
        k = r.get("rank_kind", r["kind"])
        if len(picked) < limit and per.get(k, 0) < PER_KIND:
            picked.append(r)
        per[k] = per.get(k, 0) + 1
    shown: dict[str, int] = {}
    for r in picked:
        shown[r.get("rank_kind", r["kind"])] = shown.get(r.get("rank_kind", r["kind"]), 0) + 1
    left = [f"{n - shown.get(k, 0)} more {k}" for k, n in per.items() if n > shown.get(k, 0)]
    return picked, ("and " + ", ".join(left) + " in data") if left else ""


BEATS = {"type": "array", "items": {"type": "object", "required": ["at", "expect"], "properties": {
    "at": {"type": "number", "minimum": 0}, "to": {"type": "number", "minimum": 0},
    "expect": {"type": "string", "description": " | ".join(review_beats.BEAT_KINDS)}}},
    "description": 'Beats the brief asks for, checked against the document: [{"at": 25, "to": 30, "expect": "camera move"}]. '
                   "A beat that never happens is named, and one at the wrong time (a layer already showing well before its "
                   "'shows', already whole before its 'reveals': more of it showing over at..to; a move or cut only elsewhere)."}


@tools.tool("look_review", {"properties": {**ITEM_COMP,
                                      "video": {"type": "string", "description": "An exported mp4 to read the pictures from (absolute path); faster than drawing. Default: small pictures drawn from the composition now."},
                                      "beats": BEATS,
                                      "limit": {"type": "integer", "minimum": 1, "maximum": 30, "default": 6, "description": "How many rows to write out in the summary (all are in the data). Default 6."}}})
def look_review(ctx, args):
    """What the checks measure in the film, ranked, each located with times (notes you asked for, never a verdict): a near-empty stretch; a title touching the frame
    edge; an old heading still faintly showing behind a new one; a set of parts (a chart's bars, a list's rows) not shown while
    the rest of its group is; a plain card opening empty; a character's pose barely changing for 6 s or more; an arm held nearly straight for 4 s or more;
    a character's arms or legs thin next to its body; framing held
    10 s or more (no camera move or cut); a stretch where nothing moves; a subject cut by the edge; a title, or any text line half the frame wide (a credit), inside the edge's safe margin;
    a stray small dot that later grows; a layer showing outside the screen it sits in; a lock-up whose parts touch; a washed-out stretch;
    a frame nearly empty mid-film (under 10 % covered between 15 % and 85 % of the film); opening shots that look alike (the same layers
    on the same ground, about as big); the last picture held unchanged for over a fifth of the film; a text partly crossed (10-85 %
    of it) by a layer in front for 1 s or more (a group's own background counts; fully under a panel or sheet is hidden, a frosted scrim never counts), with where to
    place the block instead (the y to type, in its parent's px); two blocks holding words (cards, panels) running into each other where they really draw, with the y that clears them; a group, picture or card that shows but is never once in the picture; words with no padding on the card behind them; the outline of a hollow ring, frame or stroked path running through a text's letters for 0.5 s or more, in front of it or behind it, even faint (a ring around the words, clear of them, is fine); a text cut by the edge of the screen or box that clips it (4-96 % of its letters outside, 1 s or more); two showing texts on top of each other (or one line printed into the next one's letters; a text on a path measured along its path); a pointer (pointer(), or a layer named cursor, pointer, mouse, finger or hand)
    covering a fifth of a label or resting on its letters; an end card whose mark or lock-up is tiny in the frame; a layer in a device's screen hanging past the screen's edge (the screen not clipping); a device (device()) cut by the frame edge
    where it is placed, or nibbled by a camera push-in while its sides show (with the camera key, the share of the film it is
    cut and a frame.fit fix; a deep push-in filling the picture is meant and only listed in data.info, with the screen texts it
    cuts); a character more than half hidden behind layers in front, or on a bare set (under 3 things or 15 % of the frame
    besides it and the background); a layer an auto layout jumps a large share of the frame in one frame with no key
    moving it (a sibling re-sized at once); and
    each declared beat (`beats`, or the ones last given to an export) that never happens or comes at the wrong time. Samples the whole film every 0.5 s in seconds. Facts, not taste: a held
    title or a planned pause may be meant: you judge."""
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
                     {"moments": rows, "info": info(faults), "every": EVERY, "samples": len(times)}, warnings=notes + more)

    if "video" in args:
        mp4 = Path(args["video"])
        if not mp4.is_file():
            raise RostrumError(codes.NOT_FOUND, ctx.tool, f'video "{mp4}"', "is not a file", hint="Give the absolute path of an mp4.")
        return finish(look_empty.scan_video(mp4))
    fps, last = comp.get("fps", 30), (round(duration * comp.get("fps", 30)) - 1) / comp.get("fps", 30)
    picks = [min(t, last) for t in times]
    scene = render.look_scene(doc, comp["id"])

    def job_fn(job):
        with tempfile.TemporaryDirectory(prefix="rostrum_review_") as tmp:
            items = [(t, Path(tmp) / f"s{i}.png") for i, t in enumerate(picks)]
            render.small_stills(ctx.tool, scene, items, look_empty.SAMPLE_W, job.progress)
            return finish(look_empty.scan_pngs(items, EVERY, duration))

    return ctx.long(f'look_review {comp["id"]}', job_fn)
