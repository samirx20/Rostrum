"""Framing and cutting (FRAME.md › Framing and cuts): `frame.fit` (frame the view, a rectangle or some layers),
`frame.cut` (a jump: Cut here, Cut to the view, Cut to these) and `frame.home`. The target is the scene's frame. Each
call is one change = one undo step. `at` is composition seconds or a shared marker ("#logo lands"): a key written
on a marker stays on it, so moving the marker moves the framing or the cut.

The keying rule of a fit: x, y and zoom (and rotation when it isn't kept) are keyed at `at`; a field with no keys yet
is also keyed at 0 s with its value now, so the frame starts where it was. At 0 s with no keys the still values just
change (the frame moves for the whole piece). `words` gives the status line for a call before it runs."""
from __future__ import annotations

from dataclasses import replace

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.keys import EASES, keys_of, marked

from . import fields as F, retime
from .evaluate import value_at
from .frame import fit as FIT, TYPE
from .kind import REGISTRY as R
from .ops_keys import put_key
from .ops_timing import _times

MOVE, ALL = ("x", "y", "zoom"), ("x", "y", "zoom", "rotation")
UNLOCKED = {"not": {"is": ["locked", True]}}
AT = Param.number("at", label="At", min=0, max=36000, unit=" s", markers=True,
                  help="The moment (composition seconds, the playhead) to key the frame at")
WHERE = {"view": "The view", "items": "These layers", "rect": "A rectangle"}
TO = [Param.choice("to", list(WHERE), label="To", labels=WHERE,
                   help="Where to: the view's rectangle, the layers `ids`, or the rectangle `rect`"),
      Param.list("ids", "id", label="Layers", help='For to "items": the layers to frame, as they show in the export at `at`'),
      Param.list("keep", "id", label="Keep whole", importance="deep",
                 help='For to "items": layers (or rig parts) that must stay whole in the frame too: the frame fits `ids` and `keep` together, '
                      'so a face with keep ["robot"] still shows the body (a tight close-up of `ids` alone cuts the rest)'),
      Param.list("rect", "number", label="Rectangle", min_items=4, max_items=4,
                 help='For to "view" / "rect": [x, y, w, h] in world px (the screen sends its visible view)'),
      Param.number("pad", label="Room", min=0, max=0.45, display="percent",
                   help="Room around, a share of the output on each side (default 5 % for layers, 0 for a rectangle)"),
      Param.toggle("keepRotation", label="Keep the turn", default=True, importance="deep")]


def _scene(ctx, fid):
    comp = ctx.item(ctx.idx[fid].parent)
    fps = float(comp.get("fps", F.defaults("comp")["fps"]))
    return fps, retime.timed(comp, _times(ctx), fps)


def _seconds(ctx, at) -> float:
    return marked.seconds(at, _times(ctx), f'{ctx.where} › "at"') if isinstance(at, str) else float(at)


def _now(timed: dict, t: float) -> dict:
    """The frame's x, y, zoom, rotation at t (seconds), markers placed."""
    frame = next(l for l in timed["layers"] if l["type"] == TYPE)
    return {f: float(value_at(frame, f, t)) for f in ALL}


def _usable(ctx, frame):
    if frame.get("ridePath"):
        ctx.fail(codes.CONFLICT, f'{frame["id"]}.ridePath', f'rides "{frame["ridePath"]}": its place comes from the path',
                 hint="layer.ride it off the path first, or move the path.")


def _goal(ctx, frame, timed, t, args, roll) -> dict:
    """{x, y, zoom[, rotation]} of the frame that frames args' `to` at t."""
    from .mcp.geometry import flatten
    to, roll = args["to"], roll if args.get("keepRotation", True) else 0.0
    size = (float(timed.get("width", 1920)), float(timed.get("height", 1080)))
    if to in ("view", "rect"):
        if "rect" not in args:
            ctx.fail(codes.BAD_ARGUMENT, '"rect"', f'is needed for to "{to}"', hint="[x, y, w, h] in world px.")
        x, y, w, h = args["rect"]
        if w <= 0 or h <= 0:
            ctx.fail(codes.BAD_ARGUMENT, f"rect {args['rect']}", "has no area", hint="Give a width and height above 0.")
        got = FIT.rect((x, y, w, h), size, roll, args.get("pad", 0.0))
    else:
        ids = args.get("ids") or []
        keep = [k for k in args.get("keep", []) if k not in ids]
        if not ids:
            ctx.fail(codes.BAD_ARGUMENT, '"ids"', 'is empty: to "items" frames one or more layers', hint="Give layer ids.")
        rows = {r["id"]: r for r in flatten({**timed, "layers": [l for l in timed["layers"] if l["type"] != TYPE]}, t)}
        groups = []
        for i in [*ids, *keep]:
            if i not in rows and i in rigged(timed):        # a part of a rig: where it is posed (the engine's place)
                groups.append((rigged(timed)[i], posed_corners(ctx, i, t)))
                continue
            if i not in rows:
                ctx.fail(codes.NOT_FOUND, f'ids "{i}"', f'is not a layer of scene "{timed["id"]}"', sorted(rows))
            top = rows[(rows[i]["within"] or (i,))[0]]
            if ctx.item(i).get("locked"):
                ctx.fail(codes.CONFLICT, f'ids "{i}"', "is locked", hint="Unlock it, or leave it out.")
            if top["props"].get("screenLock"):
                ctx.fail(codes.BAD_ARGUMENT, f'ids "{i}"', "is pinned to the frame: it shows the same wherever the frame is",
                         hint="Leave it out.")
            groups.append((top["props"].get("depth", 0.0), rows[i]["corners"]))
        home = (float(frame.get("homeX", size[0] / 2)), float(frame.get("homeY", size[1] / 2)))
        got = FIT.points(groups, size, home, roll, args.get("pad", 0.05))
        if got is None:
            ctx.fail(codes.BAD_ARGUMENT, f"ids {ids}", "are too far apart to frame at once (the zoom would go below 0.01)")
    z_lo, z_hi = FIT.ZOOM
    if not z_lo <= got[2] <= z_hi:
        ctx.fail(codes.BAD_ARGUMENT, f'{frame["id"]}.zoom', f"would be {got[2]:.4g}, outside {z_lo:g} to {z_hi:g}",
                 hint="Frame a smaller or larger area.")
    out = {"x": got[0], "y": got[1], "zoom": got[2]}
    return out if args.get("keepRotation", True) else {**out, "rotation": 0.0}


def rigged(timed: dict) -> dict[str, float]:
    """{id of a layer inside a rig: its rig's depth}: flatten stops at a rig, because the engine poses what is inside."""
    out, stack = {}, [(l, l.get("depth", 0.0)) for l in timed["layers"] if l["type"] == "rig"]
    while stack:
        node, depth = stack.pop()
        for child in node.get("layers", []):
            out[child["id"]] = depth
            stack.append((child, depth))
    return out


def posed_corners(ctx, layer_id: str, t: float) -> list:
    """The corners of a rig's part as it is posed at t, in px (frame at home: the same as world px)."""
    from . import placement
    p = placement.place_at(ctx.doc, layer_id, t)
    return [placement.comp_point(p, x, y) for x, y in ((0, 0), (p["w"], 0), (p["w"], p["h"]), (0, p["h"]))]


def _key(ctx, fid, field, at, v, **extra):
    put_key(ctx, fid, field, at, {"v": round(v, 4), **extra})


EASE = Param.choice("ease", EASES, label="Ease", importance="deep",
                    help="How the frame travels INTO this framing (the key before `at` gets it); the key names")


def _ease_into(ctx, frame, fid, f, t, ease):
    """The key of field f just before t (seconds) takes `ease`: a key's ease shapes the way to the next key."""
    times = _times(ctx)
    before = [k for k in keys_of(frame, f) if marked.seconds(k["t"], times, f"{fid}.{f}") < t - 1e-9]
    if before:
        last = max(before, key=lambda k: marked.seconds(k["t"], times, f"{fid}.{f}"))
        ctx.set(last["id"], "ease", ease)


@R.operation("frame.fit", "Frame something: `to` view or rect (the largest frame-shaped box inside `rect` [x, y, w, h], "
             "world px, keeping the frame's turn), or items (the layers `ids` as they show in the export at `at`, depth "
             "included, with `pad` room; `keep` lists layers that stay whole in the frame as well). Keys x, y, zoom at `at`; a field with no keys yet is also keyed at 0 s where "
             "it was. `ease` (a key ease name) shapes the move into it (the zoom's; x and y get the matching curve, so the "
             "move zooms about one still point and never swings off its subject). Already framed there after 0 s: its place is keyed "
             "anyway (a hold the next fit moves on from); at 0 s on a still frame nothing changes. `cut`: jump there (as "
             "frame.cut).", target=TYPE, label="Frame the view",
             valid_when=UNLOCKED, params=[replace(TO[0], required=True), *TO[1:], AT, EASE,
                                          Param.toggle("cut", label="As a cut", default=False, importance="deep")])
def frame_fit(ctx, targets, args):
    for fid in targets:
        if args.get("cut"):
            _cut(ctx, fid, args)
            continue
        frame = ctx.item(fid)
        _usable(ctx, frame)
        timed = _scene(ctx, fid)[1]
        at = args.get("at", 0.0)
        t = _seconds(ctx, at)
        goal, now = _goal(ctx, frame, timed, t, args, _now(timed, t)["rotation"]), _now(timed, t)
        if all(abs(now[f] - v) < (1e-4 if f == "zoom" else 0.01) for f, v in goal.items()):     # already framed there
            # no move, but after 0 s its place is keyed all the same (and at 0 s where it was): a hold the next fit
            # moves on from, so a script writes its shots in time order. Unkeyed, the next fit's move started at 0 s.
            if t <= 0 and not any(keys_of(frame, f) for f in goal):
                continue
        ease = args.get("ease")
        for f, v in goal.items():
            if keys_of(frame, f) or isinstance(at, str) or t > 0:
                if not keys_of(frame, f) and t > 0:
                    _key(ctx, fid, f, 0.0, float(frame.get(f, F.param(TYPE, f).default)), **({"ease": ease} if ease else {}))
                elif ease:
                    _ease_into(ctx, frame, fid, f, t, ease)
                _key(ctx, fid, f, at, v)
            else:
                ctx.set(fid, f, F.param(TYPE, f).check(round(v, 4), f"{ctx.where} › {fid}.{f}"))
        _steady(ctx, fid, t)


def _steady(ctx, fid, t):
    """The move into the key at t (seconds) zooms about one still point (frame/push.py): x and y get the curve that
    matches the zoom's, so a deep push from a wide shot never swings off its subject. Only when x, y and zoom move
    together (their keys before t at one time) and the zoom's ease is a curve; else the keys stay as eased."""
    from .frame import push
    frame, times = ctx.item(fid), _times(ctx)
    at = lambda k, f: marked.seconds(k["t"], times, f"{fid}.{f}")     # noqa: E731
    pair = {}
    for f in MOVE:
        ks = sorted(keys_of(frame, f), key=lambda k: at(k, f))
        end = next((i for i, k in enumerate(ks) if abs(at(k, f) - t) < 1e-6), None)
        if not end:
            return
        pair[f] = (ks[end - 1], ks[end])
    if len({round(at(pair[f][0], f), 6) for f in MOVE}) != 1:
        return
    zk = pair["zoom"][0]
    curve = push.ease_for(zk, float(zk["v"]), float(pair["zoom"][1]["v"]))
    if curve is None:
        return
    for f in ("x", "y"):
        for name, v in curve.items():
            ctx.set(pair[f][0]["id"], name, v)


def _cut(ctx, fid, args):
    frame = ctx.item(fid)
    _usable(ctx, frame)
    fps, timed = _scene(ctx, fid)
    at = args["at"]
    t = _seconds(ctx, at)
    if t < 1 / fps - 1e-9:
        ctx.fail(codes.BAD_ARGUMENT, f'"at" {at!r}', f"is {t:g} s: a cut needs at least one frame before it (1/{fps:g} s)",
                 hint="Cut later than the scene's start.")
    was = _now(timed, t - 1 / fps)
    new = {**was, **(_goal(ctx, frame, timed, t, args, was["rotation"]) if args.get("to") else {})}
    before = marked.moved(at, -1 / fps)          # on a marker: the marker minus one frame, so the cut moves with it
    for f in ALL:       # only what changes is keyed (a field that holds one value gets no keys: they would do nothing); a cut
                        # with no `to` is waiting for its shot, so x, y and zoom hold their place for the person's next move
        if keys_of(frame, f) or abs(new[f] - was[f]) > 1e-9 or (not args.get("to") and f in MOVE):
            _key(ctx, fid, f, before, was[f], ease="hold")
            _key(ctx, fid, f, at, new[f])


@R.operation("frame.cut", "Cut: the frame jumps at `at` (seconds or a marker). Keys its place now one frame before with "
             "the hold ease (the screen's Hold) and at `at` the same place, or with `to` (view, items or rect, as frame.fit) the new "
             "place: the jump and the next shot in one step.", target=TYPE, label="Cut here", valid_when=UNLOCKED,
             params=[replace(AT, required=True, help="Where the cut is (composition seconds, or a marker: the cut "
                                                         "follows it)"), *TO])
def frame_cut(ctx, targets, args):
    for fid in targets:
        _cut(ctx, fid, args)


@R.operation("frame.home", "Put the frame back home: its centre at home, zoom 1, no turn. A still field changes; an "
             "animated one gets a key at `at`. Already home at `at`: keyed there all the same (and at 0 s where it was, "
             "after 0 s), a hold the next fit or key moves on from, never a refusal.", target=TYPE, label="Frame home",
             importance="secondary", valid_when=UNLOCKED, params=[AT])
def frame_home(ctx, targets, args):
    for fid in targets:
        frame = ctx.item(fid)
        _usable(ctx, frame)
        at = args.get("at", 0.0)
        t = _seconds(ctx, at)
        now = _now(_scene(ctx, fid)[1], t)
        home = {"x": float(frame.get("homeX", 960.0)), "y": float(frame.get("homeY", 540.0)), "zoom": 1.0, "rotation": 0.0}
        there = all(abs(now[f] - v) < 1e-6 for f, v in home.items())
        for f, v in home.items():
            if keys_of(frame, f) or (there and f in MOVE):     # (a turn nobody asked for is never keyed)
                if not keys_of(frame, f) and t > 0:
                    _key(ctx, fid, f, 0.0, float(frame.get(f, F.param(TYPE, f).default)))
                _key(ctx, fid, f, at, v)
            else:
                ctx.set(fid, f, v)


def away(frame: dict) -> bool:
    """The `frameAway` fact (frame.home's valid when): the frame is animated or still away from home."""
    g = lambda f: frame.get(f, F.param(TYPE, f).default)  # noqa: E731
    return any(keys_of(frame, f) for f in ALL) or (g("x"), g("y"), g("zoom"), g("rotation")) != (g("homeX"), g("homeY"), 1.0, 0.0)


def words(op: str, frame: dict, args: dict, t: float) -> str:
    """The status line for `op` with `args` on `frame` as it is BEFORE the call; `t`: `at` in seconds."""
    at = args.get("at", 0.0)
    when = f"{marked.label(at)} ({t:.2f} s)" if isinstance(at, str) else f"{t:g} s"
    if op == "frame.home":
        return f"Frame home at {when}" if any(keys_of(frame, f) for f in ALL) else "Frame home"
    if op == "frame.cut" or args.get("cut"):
        cut = f"{marked.label(at)} ({t:.2f} s)" if isinstance(at, str) else f"{t:.2f} s"
        return f"Cut at {cut}." + ("" if args.get("to") else " Move the frame to the next shot.")
    fields = MOVE if args.get("keepRotation", True) else ALL
    if not isinstance(at, str) and t <= 0 and not any(keys_of(frame, f) for f in fields):
        return "Frame moved for the whole piece"
    started = t > 0 and any(not keys_of(frame, f) for f in fields)
    return f"Frame keyed at 0 s (where it was) and {when}" if started else f"Frame keyed at {when}"
