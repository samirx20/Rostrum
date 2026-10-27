"""`section.duplicate`: a copy of a section and everything that starts inside it (notes, drum hits and clips
on every track, owned by their musical place: sections.window, so a hit Humanise nudged a hair before the section's
line is copied and one a hair before its end is left to the next section), placed right after it: the copy section starts where the original ends. One operation, one
undo step; nothing after the section moves. Bars after it that already hold music (a note, hit or clip starting
there, or another section) refuse the copy, saying what is there: stacked on top it would double the music under a
hidden section. The copy is named with the next free number: "verse-2" (a copy of "verse-2" is "verse-3").
`make_room` (Ctrl+D and Repeat… on a section in the app; critic r12) first makes room right after the section, as
range.insert does (everything later moves later by the copies' length), so a middle section is copied, not refused.
`times` makes that many copies one after another (Repeat…).
"""
from __future__ import annotations

import copy
import re

from rostrum_core import Param, codes

from . import ids, sections
from .ops_range import _apply as make_time
from .repeat import TIMES
from .ops_select_move import _new_id
from .registry import REGISTRY, taken
from .select_time import moved, start_of

KINDS = {"notes": "note", "hits": "hit", "clips": "clip"}
MAKE_ROOM = Param.toggle("make_room", default=False, group="Move", label="Make room", importance="secondary",
                         help="Move everything after the section later by the copies' length first (as range.insert), "
                              "so a section with music after it is copied instead of refused.")
WORDS = {"notes": ("note", "notes"), "hits": ("drum hit", "drum hits"), "clips": ("clip", "clips")}


def _starting(root, a, b):
    """[(track id, list key, item)] for every note, hit and clip a section from `a` to `b` (seconds) owns."""
    win = sections.window(root, a, b)
    return [(tr["id"], key, it) for tr in root.get("tracks", []) for key in KINDS for it in tr.get(key, [])
            if sections.starts_in(start_of(root, it), win)]


def _in_the_way(ctx, s, b, by):
    """Refuse when the bars the copy would fill already hold music or another section, naming what is there. The
    music there is what a section in those bars would own (the same window), so the next section's own early hits
    never refuse a copy that ends at its line."""
    root = ctx.doc
    there = _starting(root, b, b + by)
    counts = {k: sum(1 for _, key, _ in there if key == k) for k in KINDS}
    what = [f"{n} {WORDS[k][n != 1]}" for k, n in counts.items() if n]
    secs = [x.get("name") or x["id"] for x in root.get("sections", []) if x["id"] != s["id"]
            and start_of(root, x) < b + by - 1e-6 and start_of(root, {**x, "at": x["end"]}) > b + 1e-6]
    what += [f"the section {', '.join(secs)}"] if secs else []
    if what:
        said = ", ".join(what[:-1]) + (" and " if len(what) > 1 else "") + what[-1]
        ctx.fail(codes.BAD_ARGUMENT, f'"{s["id"]}"', f"the bars right after it already have {said}",
                 hint="Move what follows later first (section.move on the sections after it), then duplicate.",
                 plain=f"The bars after {s.get('name') or s['id']} already have {said}: a copy would sit on top. "
                       "Move what follows later first.")


def _copy_name(s, root, ctx):
    """("verse-2", "section.verse-2"): the original's name without its number, then the first free number (a copy of
    verse-2 is verse-3, never verse-2-2). A name can't hold a space (the section name check), so the number joins with
    "-", as a new section's "part-7" does (an "_2" reads as a made-up name: the panel called it "Section 2")."""
    base = re.sub(r"[-_]\d+$", "", s.get("name") or "section")
    names, have = {x.get("name") for x in root.get("sections", [])}, taken(ctx)
    n = 2
    while f"{base}-{n}" in names or f"section.{base}-{n}" in have:
        n += 1
    return f"{base}-{n}", f"section.{base}-{n}"


@REGISTRY.operation("section.duplicate", "Copy sections with everything that starts inside them to right after "
                    "each (the copy is named like it, with the next free number: verse-2); one step. A note, hit or "
                    "clip nudged up to a 1/32 note before the section's line counts as inside (one that close to its "
                    "end belongs to the next section). Refused when the bars after it "
                    "already have music or another section (it says what is there), unless make_room moves them later first. "
                    "times: that many copies, one after another.", target="section",
                    params=[TIMES, MAKE_ROOM], label="Duplicate section")
def duplicate(ctx, targets, args):
    n = int(args.get("times", 1))
    for t in sorted(targets, key=lambda t: -start_of(ctx.doc, ctx.item(t))):    # the latest first: room made for one never moves another's
        s = ctx.item(t)
        a, b = start_of(ctx.doc, s), start_of(ctx.doc, {**s, "at": s["end"], "id": t})
        if args.get("make_room"):                 # the room starts at its end, which stays put (never grows with it)
            end = s["end"]
            make_time(ctx, b, b + n * (b - a), True)
            if ctx.item(t)["end"] != end:
                ctx.set(t, "end", end)
        for k in range(n):
            _copy(ctx, ctx.item(t), a, b, round((k + 1) * (b - a), 6), k)


def _copy(ctx, s, a, b, by, k):
    """The k-th copy (from 0) of section `s` (from `a` to `b` s) and everything it owns, `by` seconds later."""
    root, t = ctx.doc, s["id"]
    _in_the_way(ctx, s, a + by, b - a)
    for track, key, it in _starting(root, a, b):
        new = copy.deepcopy(it)
        new["at"] = moved(ctx, it, by)
        new["id"] = _new_id(KINDS[key], track, new, ctx)
        for fx in new.get("effects", []):
            fx["id"] = ids.effect(new["id"], fx.get("effect", "effect"), taken(ctx) | {new["id"]})
        ctx.insert(track, key, new)
    name, id_ = _copy_name(s, root, ctx)
    copy_ = {**copy.deepcopy(s), "id": id_, "name": name, "at": moved(ctx, s, by),
             "end": moved(ctx, {**s, "at": s["end"]}, by)}
    ctx.insert("root", "sections", copy_, ctx.idx[t].index + 1 + k)
