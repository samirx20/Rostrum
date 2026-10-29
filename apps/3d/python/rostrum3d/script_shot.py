"""Framing and lighting by intent in a script (script.py), on the same maths as the operations (ops_shot_camera.py).

- `shot(id, camera=cam, frame=item_or_list, at=(1/3, 0.5), fill=0.6)`: the shot's camera keeps the way it looks and its
  lens and moves so the subject's middle lands at `at` (fractions of the picture from the left and from the top;
  default the middle) and its height takes `fill` of the picture's height (default 0.6). An aimed camera stops aiming
  and keeps the turn it had (its aim becomes its plain turn), so the subject stays where it was put.
  `shot.key("frame", {0: {"fill": 0.4}, 3: {"fill": 0.8}})`: the same at each time (a push-in), written as ordinary
  x y z keys on the camera; each time's dict may also give "at" and "frame" (the subject); left out, shot()'s.
- `cam.take_view(pos, look_at)`: the camera stands at `pos` (world) and aims at `look_at` (a point or an item).
- `light(..., brightness=0, at_distance=None)`: brightness in stops against the start key light: 0 lights the
  subject as the new scene's key light does its subject, +1 twice that, −1 half. It sets the light's intensity
  (Same brightness at any size on, scaled with the distance squared) and its exposure (= the stops). The distance is
  `at_distance` (metres to the subject), else from the light to what it aims at. A dome: exposure = the start sky's
  (start_scene.SKY_EXPOSURE) + stops. A distant (sun) light has no distance: give its intensity.
"""
from __future__ import annotations

import math

from . import aim, ops_shot_camera as SC, start_scene
from .resolve import Frames

START_KEY = {"intensity": float(start_scene.KEY_INTENSITY), "distance": math.dist(start_scene.KEY_AT, start_scene.KEY_AIM)}
START_SKY_EXPOSURE = start_scene.SKY_EXPOSURE


def _scene(b) -> dict:
    from .script_figure import _scene
    return _scene(b)


def _ids(subject) -> list[str]:
    items = subject if isinstance(subject, (list, tuple)) else [subject]
    return [getattr(i, "id", i) for i in items]


def frame(b, shot: dict, settings: dict, t: float | None = None):
    """Move the shot's camera to frame settings["frame"] (see the module's note); a key at `t` when given."""
    who = f"shot {shot['id']!r}"
    if not shot.get("camera"):
        raise ValueError(f"{who}: frame= moves the shot's camera; give it one: shot(..., camera=cam)")
    cam = b.edit(shot["camera"])
    ids, at = _ids(settings["frame"]), settings.get("at", (0.5, 0.5))
    fill = float(settings.get("fill", 0.6))
    if not (len(at) == 2 and all(0.0 <= float(a) <= 1.0 for a in at)) or not 0.0 < fill <= 4.0:
        raise ValueError(f"{who}: at=(x, y) is fractions of the picture from the left and the top, each 0..1 "
                         f"(e.g. (1/3, 0.5)); fill is the subject's share of the picture's height, e.g. 0.6")
    when = float(shot.get("start", 0.0) if t is None else t)
    f = round(when * 1000)
    data = _scene(b)
    fr = Frames(data, range(f, f + 1), 1000.0)
    eye, axes, tan_w, tan_h, v = SC.view(fr, cam.id, f, shot)
    from . import item_bounds
    try:
        lo, hi = item_bounds.world_box(data, ids, when)
    except (ValueError, KeyError) as e:
        raise ValueError(f"{who}: frame={ids}: {e}") from None
    corners = item_bounds._corners(lo, hi)
    new = SC.subject_eye(axes, corners, tan_w, tan_h, 2 * v["near"], tuple(map(float, at)), fill)
    pw, local = SC._place(fr, cam.id, f, new)
    if v.get("aim", "none") != "none":                     # keep the direction it looks in now, as a plain turn
        turn = aim.aim_rotation(pw, [local[k] for k in "xyz"], [n + d for n, d in zip(new, axes[2])])
        cam.set(aim="none", **{k: round(r, 4) for k, r in zip(("rx", "ry", "rz"), turn)})
    if t is None:
        cam.set(**local)
    else:
        for k in "xyz":
            cam.key(k, {when: local[k]}, ease=settings.get("ease", "smooth"))


def key_frame(b, shot: dict, base: dict, keys: dict, ease: str):
    if not isinstance(keys, dict) or not keys:
        raise ValueError(f'shot {shot["id"]!r}.key("frame", …): keys are {{seconds: {{"fill": 0.4, "at": (1/3, 0.5)}}}}')
    for t, own in sorted(keys.items()):
        settings = {**base, "ease": ease, **(own if isinstance(own, dict) else {"fill": own})}
        if "frame" not in settings:
            raise ValueError(f'shot {shot["id"]!r}.key("frame", …): say what to frame: shot(..., frame=item) or '
                             f'{{t: {{"frame": item, "fill": …}}}}')
        frame(b, shot, settings, float(t))


def take_view(item, pos, look_at):
    """cam.take_view: stand at `pos` (world) and aim at `look_at` (a point or an item)."""
    b, node = item._b, item.node
    if node["type"] != "camera":
        raise ValueError(f"{item.id} is a {node['type']}; .take_view() is for a camera")
    data = _scene(b)
    fr = Frames(data, range(0, 1), 1.0)
    parent = fr.parent.get(item.id)
    pw = fr.world(parent, 0) if parent else aim.IDENTITY
    local = aim.point(aim.invert(pw), [float(c) for c in pos])
    item.set(**{k: round(v, 6) + 0.0 for k, v in zip("xyz", local)})
    return item.aim(tuple(look_at) if isinstance(look_at, (list, tuple)) else look_at)


def brightness(b, node: dict, stops: float, at_distance=None):
    """A light's intensity and exposure from brightness= stops (see the module's note); called when the script ends."""
    who = f"light {node['id']!r}"
    if node.get("kind") == "dome":
        node.update(exposure=round(START_SKY_EXPOSURE + stops, 4))
        return
    if node.get("kind") == "distant":
        raise ValueError(f"{who}: a distant light (the sun) is as bright everywhere; give intensity= (about 3) instead of brightness=")
    d = at_distance
    if d is None:
        if node.get("aim", "none") == "none":
            raise ValueError(f"{who}: brightness= needs at_distance= (metres from the light to its subject) or an aim")
        fr = Frames(_scene(b), range(0, 1), 1.0)
        target = ([node["aimX"], node["aimY"], node["aimZ"]] if node["aim"] == "point"
                  else aim.point(fr.world(node["aimItem"], 0), [0.0, 0.0, 0.0]))
        d = math.dist(aim.point(fr.world(node["id"], 0), [0.0, 0.0, 0.0]), target)
    if float(d) <= 0:
        raise ValueError(f"{who}: at_distance must be more than 0 metres")
    node.update(normalize=True, exposure=round(float(stops), 4),
                intensity=round(START_KEY["intensity"] * (float(d) / START_KEY["distance"]) ** 2, 4))


def make(b, id_, values: dict):
    """shot(...): a shot, framed when frame= is given; made again under an id in the scene, it keeps its camera."""
    framing = {k: values.pop(k) for k in ("frame", "at", "fill") if k in values}
    if framing and "frame" not in framing:
        raise ValueError("shot(...): at= and fill= say where the subject sits; name it too: frame=item (or a list)")
    it = b.add("shot", id_, values, b.root["shots"])
    if not it.node.get("camera") and b.doc is not None:          # shot("shot_1", end=3) keeps shot_1's camera
        was = next((s for s in b.doc.data.get("shots", []) if s.get("id") == it.id), None)
        if was is not None and was.get("camera"):
            it.node["camera"] = was["camera"]
    if framing:
        b.framing[it.id] = framing
        frame(b, it.node, framing)
    return it


def default_view(b):
    """A shot the script gave no camera is seen through the default view: the new scene's camera (55 cm up, 1.6 m back,
    50 mm, looking at the middle of the ground), `<shot>_camera`, made unless the scene already has it; the run's
    reply says so (b.notes). Never refused: what the script wrote stays as written."""
    from rostrum_core.tree import walk
    from .kind import KIND
    for s in b.root.get("shots", []):
        if s.get("camera"):
            continue
        cam = f'{s["id"]}_camera'
        made = any(n.get("id") == cam for n in walk(b.root, KIND.lists))
        mine = any(n.get("id") == cam for n in walk(b.doc.script_bases.get(b.name) or {}, KIND.lists)) if b.doc is not None else False
        there = b.doc is not None and any(n.get("id") == cam and n.get("type") == "camera" for n in walk(b.doc.data, KIND.lists))
        if not made and (mine or not there):
            b.item("camera", cam, name=f'{s.get("name") or s["id"]} camera', focalLength=50, y=0.55, z=1.6).aim((0, 0.12, 0))
        s["camera"] = cam
        b.given.setdefault(s["id"], set()).add("camera")
        b.notes.append(f'shot "{s["id"]}" has no camera: it is seen through the default view, camera "{cam}" '
                       "(55 cm up, 1.6 m back, looking at the middle of the ground); give it yours with shot(..., camera=cam)")
