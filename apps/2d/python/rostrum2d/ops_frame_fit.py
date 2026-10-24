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
from rostrum_core.keys import keys_of, marked

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
        if not ids:
            ctx.fail(codes.BAD_ARGUMENT, '"ids"', 'is empty: to "items" frames one or more layers', hint="Give layer ids.")
        rows = {r["id"]: r for r in flatten({**timed, "layers": [l for l in timed["layers"] if l["type"] != TYPE]}, t)}
        groups = []
        for i in ids:
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


def _key(ctx, fid, field, at, v, **extra):
    put_key(ctx, fid, field, at, {"v": round(v, 4), **extra})


@R.operation("frame.fit", "Frame something: `to` view or rect (the largest frame-shaped box inside `rect` [x, y, w, h], "
             "world px, keeping the frame's turn), or items (the layers `ids` as they show in the export at `at`, depth "
             "included, with `pad` room). Keys x, y, zoom at `at`; a field with no keys yet is also keyed at 0 s where "
             "it was. `cut`: jump there (as frame.cut).", target=TYPE, label="Frame the view",
             valid_when=UNLOCKED, params=[replace(TO[0], required=True), *TO[1:], AT,
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
        if all(abs(now[f] - v) < (1e-4 if f == "zoom" else 0.01) for f, v in goal.items()):     # keys that change nothing: none written
            ctx.fail(codes.CONFLICT, f'target "{fid}"', f"is already framed there at {marked.label(at)}",
                     hint="Nothing was keyed: the frame already shows this.")
        for f, v in goal.items():
            if keys_of(frame, f) or isinstance(at, str) or t > 0:
                if not keys_of(frame, f) and t > 0:
                    _key(ctx, fid, f, 0.0, float(frame.get(f, F.param(TYPE, f).default)))
                _key(ctx, fid, f, at, v)
            else:
                ctx.set(fid, f, F.param(TYPE, f).check(round(v, 4), f"{ctx.where} › {fid}.{f}"))


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
    for f in ALL:
        _key(ctx, fid, f, before, was[f], ease="hold")
        _key(ctx, fid, f, at, new[f])


@R.operation("frame.cut", "Cut: the frame jumps at `at` (seconds or a marker). Keys its place now one frame before with "
             "the hold ease (Jump) and at `at` the same place, or with `to` (view, items or rect, as frame.fit) the new "
             "place: the jump and the next shot in one step.", target=TYPE, label="Cut here", valid_when=UNLOCKED,
             params=[replace(AT, required=True, help="Where the cut is (composition seconds, or a marker: the cut "
                                                         "follows it)"), *TO])
def frame_cut(ctx, targets, args):
    for fid in targets:
        _cut(ctx, fid, args)


@R.operation("frame.home", "Put the frame back home: its centre at home, zoom 1, no turn. A still field changes; an "
             "animated one gets a key at `at`.", target=TYPE, label="Frame home", importance="secondary",
             valid_when={"all": [UNLOCKED, {"fact": "frameAway"}]}, params=[AT])
def frame_home(ctx, targets, args):
    for fid in targets:
        frame = ctx.item(fid)
        _usable(ctx, frame)
        at = args.get("at", 0.0)
        now = _now(_scene(ctx, fid)[1], _seconds(ctx, at))
        home = {"x": float(frame.get("homeX", 960.0)), "y": float(frame.get("homeY", 540.0)), "zoom": 1.0, "rotation": 0.0}
        if all(abs(now[f] - v) < 1e-6 for f, v in home.items()):
            ctx.fail(codes.BAD_ARGUMENT, f'target "{fid}"', f"is already home at {marked.label(at)}")
        for f, v in home.items():
            if keys_of(frame, f):
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
