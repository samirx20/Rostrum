"""The compiler: one shot of the document → the scene description the C++ core builds its USD stage from
(ENGINE_CONTRACT.md § 2). Every field is present (defaults filled in), colours are linear, aims, sticks and follows
are turned into x … sz (resolve.py, follow.py), a mirrored copy into a plain mesh (mirror.py), and every animated field is baked to one value per frame, start..end inclusive, at the shot's fps (an item
on 2s or 3s, its `timing`, holds each value for 2 or 3 frames, counted from the shot's start).
Frame n is at n / fps seconds; the one evaluator and easing are rostrum_core.keys' (the same keys as 2D).
"""
from __future__ import annotations

from . import aim, clay_scene, fields as F, follow, material_scene, mirror, skies, outline as outlines, paint_scene, rigs, skin
from .resolve import PIVOT, TIMING, Frames as _Frames, pivoted, world_at_start  # noqa: F401  (world_at_start: ops)
from .outline_fields import FIELDS as _OUTLINE_PARAMS, OUTLINE_SHAPES
from .colors import linear
from .light_fields import DOC_ONLY as LIGHT_DOC_ONLY
from .render_fields import shutter_frames

FORMAT, VERSION = "rostrum-3d-scene", 1
AIM_FIELDS = {"aim", "aimX", "aimY", "aimZ", "aimItem", "roll"}      # document-only: the compiler resolves them
ROTATION = ("rx", "ry", "rz")
FOCUS_ITEM = "focusItem"                       # a camera's: the compiler turns it into focusDistance per frame
CONSTRAINTS = {"follow", "followAmount", "stick"}             # follow.py: resolved into x … sz
SKINNED = "skinned"                            # a mesh's Bend with bones: sent as its `skin` (skin.py), never as a prop
POSE = {"jointNames", "holds", "jointsKey"}    # a clay's joint settings: the document's alone (ops_pose.py)
FILE_UNIT = "fileUnit"                         # an import's: what its file was in, for Keep original size (ops_import.py)
RESOLVED = AIM_FIELDS | set(PIVOT) | CONSTRAINTS | POSE | set(mirror.FIELDS) | {FOCUS_ITEM, TIMING, SKINNED, FILE_UNIT}   # resolved, never sent
DOCUMENT_ONLY = {p.name for p in _OUTLINE_PARAMS if p.group == "Shape"} | {"paintSize"}   # words, font, file … never sent


def _shot(data: dict, shot_id: str) -> dict:
    shots = data.get("shots", [])
    shot = next((s for s in shots if s["id"] == shot_id), None)
    if shot is None:
        raise ValueError(f'no shot "{shot_id}"; there are: {", ".join(s["id"] for s in shots) or "none (shot.add)"}')
    return shot


def shot_info(data: dict, shot_id: str) -> dict:
    """{id, camera (item id), fps, start, end (frames, inclusive), width, height} of a shot."""
    s = _shot(data, shot_id)
    start, end = round(s["start"] * s["fps"]), round(s["end"] * s["fps"]) - 1
    if not s.get("camera"):
        raise ValueError(f'shot "{shot_id}" has no camera yet (shot.set camera=<camera id>)')
    if end < start:
        raise ValueError(f'shot "{shot_id}" is shorter than one frame at {s["fps"]} fps')
    return {"id": s["id"], "camera": s["camera"], "fps": s["fps"], "start": start, "end": end,
            "width": s["width"], "height": s["height"]}


def _focus_on_item(id_: str, fr: _Frames) -> list[float] | None:
    """A camera's focus distance per frame while it focuses on an item (focusItem): how far in front of the camera
    (along its −Z, the way a lens measures it) the item's origin is. None when it focuses on a distance."""
    v0 = fr.values(id_, fr.frames[0])
    target = v0.get(FOCUS_ITEM) or ""
    if not v0["dof"] or not target:
        return None
    if target not in fr.items:
        raise ValueError(f'{id_}: focuses on "{target}", which is not an item')
    return [max(0.001, aim.ahead(fr.world(id_, f), aim.point(fr.world(target, f), [0.0, 0.0, 0.0]))) for f in fr.frames]


def _out(p, value):
    if p.type == "color":
        return linear(value)
    if p.type == "toggle":
        return bool(value)                         # a keyed Visible: True / False per frame (F.toggle_at)
    return round(value, 6) if isinstance(value, float) else value


def _rig_node(item: dict, fr: _Frames) -> dict:
    """A rig goes to the core as a group whose transform is baked per frame (rigs.py)."""
    params = [p for p in F.FIELDS["group"] if p.name not in RESOLVED]
    per_frame = {p.name: [fr.values(item["id"], f)[p.name] for f in fr.frames] for p in params}
    turns = rigs.continuous(list(zip(*(per_frame[r] for r in ROTATION))))
    for i, r in enumerate(ROTATION):
        per_frame[r] = [t[i] for t in turns]
    node = {"id": item["id"], "type": "group", "props": {p.name: _out(p, per_frame[p.name][0]) for p in params}}
    anim = {k: [_out(F.param("group", k), x) for x in vals] for k, vals in per_frame.items()
            if max(vals) - min(vals) > 1e-9}
    if anim:
        node["anim"] = anim
    node["children"] = [_node(c, fr) for c in item.get("children", [])]
    return node


def _outline_props(id_: str, values: dict, props: dict, folder):
    """A text / svg / path2d mesh goes to the core as shape "outline": the flattened outline in metres, and none of the
    fields that only the document needs (the words, the font, the file …)."""
    outline = outlines.for_item({**values, "id": id_}, folder)
    for name in DOCUMENT_ONLY:
        props.pop(name, None)
    props["shape"], props["outline"] = "outline", outline


def _node(item: dict, fr: _Frames) -> dict:
    if item["type"] == "rig":
        return _rig_node(item, fr)
    type_, first = item["type"], fr.frames[0]
    params = [p for p in F.FIELDS[type_] if p.name not in RESOLVED
              and not (type_ == "light" and p.name in LIGHT_DOC_ONLY)]
    v0 = fr.values(item["id"], first)
    node = {"id": item["id"], "type": type_, "props": {p.name: _out(p, v0[p.name]) for p in params}}
    if type_ == "light" and v0["kind"] == "dome":
        node["props"]["texture"] = skies.path(v0["texture"])   # "sky:studio": the sky that comes with the app (skies/)
    if type_ == "mesh" and v0["shape"] in OUTLINE_SHAPES:
        _outline_props(item["id"], v0, node["props"], fr.folder)
    elif type_ == "mesh":
        for name in DOCUMENT_ONLY:
            node["props"].pop(name)
    copy_of = fr.items.get(item.get("mirror") or "")             # a mirrored copy is keyed by its original's keys
    animated = {k["prop"] for k in (copy_of or item).get("keys", [])} - RESOLVED
    if any(v0.get(p) for p in PIVOT) and animated & {"rx", "ry", "rz", "sx", "sy", "sz", *PIVOT}:
        animated |= {"x", "y", "z"}                            # the origin moves as it turns around its pivot
    if type_ == "light" and v0["kind"] == "dome" and "turn" in animated:
        animated.add("ry")
    worked = set(ROTATION if item.get("aim", "none") != "none" else ()) | set(follow.TRS if item.get("follow") else ())
    if item.get("stick"):
        worked |= {"x", "y", "z"}                              # fields worked out per frame (resolve.py)
    if copy_of:
        worked |= set(follow.TRS)                              # placed through the mirror, per frame (mirror.py)
    per_frame = {r: [fr.values(item["id"], f)[r] for f in fr.frames] for r in worked}
    animated |= {r for r, vals in per_frame.items() if max(vals) - min(vals) > 1e-9}
    anim = {}
    for p in params:
        if p.name in animated:
            vals = per_frame.get(p.name) or [fr.values(item["id"], f)[p.name] for f in fr.frames]
            anim[p.name] = [_out(p, x) for x in vals]
    if type_ == "camera" and (focus := _focus_on_item(item["id"], fr)) is not None:
        p = F.param("camera", "focusDistance")
        node["props"]["focusDistance"] = _out(p, focus[0])
        anim.pop("focusDistance", None)
        if max(focus) - min(focus) > 1e-9:
            anim["focusDistance"] = [_out(p, x) for x in focus]
    if anim:
        node["anim"] = anim
    if type_ in ("mesh", "clay") and v0[SKINNED] and (bent := skin.skin(item, skin.frame_times(fr, item["id"]))):
        node["skin"] = bent                                    # its bones go only as the skin (skin.py), never as nodes
    if type_ == "clay":
        clay_scene.finish(node, item, fr.folder, fr.data)      # its steps, keyed, and its cache (clay_scene.py)
    if type_ == "import":
        node["props"]["parts"] = [{"path": pt["path"], "material": pt["material"], "visible": pt["visible"]}
                                  for pt in item.get("parts", [])]
    if type_ in F.HOLDERS:
        node["children"] = [_node(c, fr) for c in item.get("children", [])]
    return node


def describe(data: dict, shot_id: str, folder=None) -> dict:
    """The contract § 2 scene of one shot. `folder`: the project folder (a path2d mesh reads its 2D document there)."""
    info, shot = shot_info(data, shot_id), _shot(data, shot_id)
    frames = range(info["start"], info["end"] + 1)
    fr = _Frames(data, frames, info["fps"], folder)
    cam = fr.items.get(info["camera"])
    if cam is None or cam["type"] != "camera":
        raise ValueError(f'shot "{shot_id}": its camera "{info["camera"]}" is not a camera in this document')
    scene = {
        "format": FORMAT, "version": VERSION,
        # shutter: frames the shutter is open, centred on each frame (USD's camera shutter is frame-relative and
        # Cycles' default motion position is the centre), so the sharp picture of frame n sits in the middle of its
        # smear and a still frame matches the unblurred one at its own time.
        "shot": {**{k: info[k] for k in ("id", "fps", "start", "end")}, "shutter": shutter_frames(shot)},
        "world": {"background": linear(shot["background"]), "environment": None},
        "materials": material_scene.materials(data, frames, info["fps"], folder, _out),
        "items": [_node(i, fr) for i in data.get("items", [])],
    }
    paint_scene.paint(scene, data, _out)          # painted meshes get their own material with the painted pictures
    return scene
