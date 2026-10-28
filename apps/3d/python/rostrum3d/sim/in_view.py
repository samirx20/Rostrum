"""sim.start_in_view: raise (or lower) a falling thing or a cloth so it starts inside the shot camera's picture, its top
a chosen share of the picture's height below the picture's top edge, at the frame it starts falling (Falls from) as the
shot camera sees it then. Only its height changes: it falls straight down from where it was, now in view.

    dy = lift(doc.data, "sweets", "spill", from_top=0.1)        # metres to add to its y (the operation does it)
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.keys.evaluate import keys_of

from ..kind import REGISTRY as R
from ..motion_track import Camera
from ..resolve import Frames
from . import fields as SF
from .inputs import value

FROM_TOP = 0.1          # default: its top a tenth of the picture's height below the top edge
FAR = 1000.0            # m: past this up or down the camera never shows it there


class NotInView(ValueError):
    """Why it can't be put in view (the reason and what to do)."""


def _screen_y(cam: Camera, p, dy: float):
    s = cam.project([p[0], p[1] + dy, p[2]])
    return None if s is None else s[1]


def _solve(cam: Camera, p, target: float) -> float:
    """dy that puts world point p (moved up by dy) at picture height `target` (px from the top)."""
    def h(dy):
        y = _screen_y(cam, p, dy)
        return None if y is None else y - target
    h0 = h(0.0)
    if h0 is None:
        raise NotInView("it is behind the shot camera: move it in front of the camera first")
    if abs(h0) < 0.5:
        return 0.0
    rise = h(0.01)
    if rise is None or abs(rise - h0) < 1e-6:
        raise NotInView("the shot camera looks straight down at it, so its height doesn't move it in the picture: "
                        "set its height by hand (y)")
    way = 1.0 if (h0 > 0) == (rise < h0) else -1.0                  # up when that moves it towards the target
    lo, d = 0.0, 0.05
    while True:
        hd = h(way * d)
        if hd is None or d > FAR:
            raise NotInView("the camera never shows it at that height (it would pass over or behind the camera): "
                            "turn the camera or give a larger fromTop")
        if (hd > 0) != (h0 > 0):
            break
        lo, d = d, d * 2
    hi = d
    for _ in range(60):
        mid = (lo + hi) / 2
        hm = h(way * mid)
        if hm is None or (hm > 0) != (h0 > 0):
            hi = mid
        else:
            lo = mid
    return way * (lo + hi) / 2


def start_frame(data: dict, item: dict, info: dict) -> int:
    """The shot frame it starts falling: its Falls from."""
    wake = round(float(value(item, "fallStart")) * info["fps"])
    return min(info["start"] + max(wake, 0), info["end"])


def lift(data: dict, item_id: str, shot_id: str, from_top: float = FROM_TOP, folder=None) -> float:
    """Metres to add to the item's y so its top sits `from_top` of the picture's height below the picture's top edge,
    as the shot camera sees it at the frame it starts falling. NotInView with the reason when the camera can't show it."""
    from ..compile import _shot, shot_info
    from ..item_bounds import world_box
    info = shot_info(data, shot_id)
    item = next(i for i in data.get("items", []) if i["id"] == item_id)
    f = start_frame(data, item, info)
    fr = Frames(data, range(f, f + 1), info["fps"], folder)
    cam = Camera(fr, info["camera"], f, info["width"], info["height"])
    (lx, ly, lz), (hx, hy, hz) = world_box(data, [item_id], f / info["fps"])
    top = [(lx + hx) / 2, hy, (lz + hz) / 2]
    dy = _solve(cam, top, from_top * info["height"])
    x = cam.project([top[0], hy + dy, top[2]])[0]
    if not 0 <= x <= info["width"]:
        raise NotInView(f"it is beside the picture ({'left' if x < 0 else 'right'} of it), so no height puts it in view: "
                        "move it sideways into the shot first (x, z)")
    if ly + dy < 0 and _shot(data, shot_id).get("simGround", True):
        raise NotInView("there the top of the picture is below the floor: raise or tilt the camera, or move the thing "
                        "farther from the camera")
    if dy < 0 and (inside := _starts_inside(data, item_id, ((lx, ly + dy, lz), (hx, hy, hz)), f / info["fps"])):
        raise NotInView(f"that low it would start inside or under {inside} (what it falls onto): give a smaller "
                        "fromTop, or raise or tilt the camera")
    return dy


def _starts_inside(data: dict, item_id: str, box, t: float) -> str:
    """The first other simulated thing whose box the room it moves down through overlaps ("" when none)."""
    from ..item_bounds import world_box
    from .inputs import bodies
    (lx, ly, lz), (hx, hy, hz) = box
    for b in bodies(data):
        if b["id"] == item_id:
            continue
        try:
            (ox, oy, oz), (px, py, pz) = world_box(data, [b["id"]], t)
        except ValueError:
            continue
        if lx < px and ox < hx and lz < pz and oz < hz and ly < py and oy < hy:
            return b["id"]
    return ""


@R.operation("sim.start_in_view", "Move things set to Falls or Cloth up (or down) so each starts inside the shot camera's "
             "picture: its top fromTop of the picture's height below the picture's top edge (0.1 default; 0 = touching "
             "the top edge, 0.5 = halfway down), as the shot camera sees it at the frame it starts falling (its fallStart, "
             "Falls from). Only its height (y) changes, so it falls straight down from where it was, now in view: a fall "
             "dropped from above the picture is seen whole, and a thing that started on what it should land on gets "
             "a drop. A copies item moves as a whole (its highest copy goes there). Fails with the reason when no height "
             "can show it (beside the picture, behind the camera, the camera looking straight down, the picture's top "
             "below the floor) or when its height has keys. Check the result with look_motion (says how many frames each "
             "fall is on screen).", target=SF.TYPES, label="Start in view", importance="secondary",
             params=[Param.number("fromTop", label="From the top", min=0, max=0.9, step=0.01, default=FROM_TOP,
                                  help="Where its top starts, as a share of the picture's height below its top edge"),
                     Param.text("shot", label="Shot", help="The shot whose camera it starts in view of (default: the "
                                                           "only shot, else the first)")])
def sim_start_in_view(ctx, targets, args):
    shots = ctx.doc.get("shots", [])
    shot = args.get("shot") or (shots[0]["id"] if shots else "")
    if not shot:
        ctx.fail(codes.BAD_ARGUMENT, '"shot"', "is missing and the scene has no shot", hint="Make a shot with a camera first.")
    for t in targets:
        item = ctx.item(t)
        if value(item, "simulate") not in ("falls", "cloth"):
            ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', "neither falls nor is cloth", hint="Set Simulate › Falls or Cloth first (sim.body).")
        if keys_of(item, "y"):
            ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', "has keys on its height (y), and a key sets where it starts",
                     hint="Remove its y keys first, or move its first y key yourself.")
        try:
            dy = lift(ctx.doc, t, shot, float(args.get("fromTop", FROM_TOP)), getattr(ctx.doc, "folder", None))
        except NotInView as e:
            ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', f"can't start in view of shot \"{shot}\": {e}")
        except ValueError as e:
            ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', str(e))
        ctx.set(t, "y", round(float(item.get("y", 0.0)) + dy, 4))
