"""The scene description: what the Python layer sends the engine (ENGINE_CONTRACT.md). One composition, every
item's still values with defaults filled in, and the keys of its animated fields; the engine evaluates them per
frame (the evaluation's reference is evaluate.py). A field with an expression (exprbake.py) is sent as linear keys,
one per frame, in place of its own keys; so is a field an auto layout sets (layoutbake.py), over both. A stepped
item's ("on twos", stepped.py) animated fields are then sent as hold keys every n frames. A swap set (swap.py) is
sent as a plain group whose children's opacity shows one at a time; a 3D render layer (render3d.py) is
sent as a video layer over the render's frames. A layer timed from a shared marker (retime.py) has its times
made composition times first. The layout and swap fields themselves stay on
the Python side (`python_only`): the engine never sees them. Rigs, long IK chains included, are the engine's.
"""
from __future__ import annotations

import math
from functools import lru_cache

from . import drawing, group_bg, missing_font, exprbake, fields as F, fill_fields, fill_paint, layoutbake, looping, media, paint_fields, painted_fill, project_sound, render3d, retime, stepped, swap, video
from .layout_fields import py_only
from rostrum_core import RostrumError
from rostrum_core.errors import codes
from rostrum_core.keys import after, animated, keys_of, springs
from rostrum_paint import library

FORMAT, VERSION = "rostrum-2d-scene", 3      # 2: the scene's frame (FRAME.md) in place of cameras; 3: picture / painted fill per use


KEY_FIELDS = ("t", "v", "c", "d", "ease", "x1", "y1", "x2", "y2", "stiffness", "damping", "out", "in")   # out / in: spatial handles


@lru_cache(maxsize=None)
def python_only(kind: str) -> frozenset[str]:
    """The fields of an item type the engine never sees: auto layout's, stepped timing's and swap sets' (all
    applied here), the scene's soundtrack (Sound's engine plays it, not 2D's) and a text's style link (its values are
    already on the text: text_styles.py). Fixed per type: worked out once (a scene asks for it per field)."""
    return frozenset(py_only(kind) | {stepped.FIELD, retime.FIELD, retime.END, "locked", "hidden", "eachFrame", "newHold", "soundtrack", "textStyle"} | ({"loop"} if kind == "drawing" else set()) | (group_bg.NAMES if kind == "group" else set()) | swap.PY_ONLY.get(kind, set())
            | paint_fields.NAMES | fill_fields.NAMES)


def _key(key: dict) -> dict:
    """A key as the engine reads it: a spring written as bounce / speed goes as its stiffness / damping (springs)."""
    out = {k: key[k] for k in KEY_FIELDS if k in key}
    if key.get("ease") == "spring" and ("bounce" in key or "speed" in key):
        out["stiffness"], out["damping"] = springs.physics_of(key)
    return out


def _anim(item: dict, until: float) -> dict:
    """Each animated field's keys; a last key's "after the last key" goes written out as plain keys up to `until`, the
    composition's end (rostrum_core.keys.after: the engine reads keys only)."""
    return {prop: _keys(item, prop, until) for prop in sorted(animated(item)) if prop not in python_only(item["type"])}


def _keys(item: dict, prop: str, until: float) -> list[dict]:
    """One field's keys as the engine reads them (empty when it isn't animated)."""
    return [_key(key) for key in after.extend(keys_of(item, prop), until)] if prop in animated(item) else []


def _node(item: dict, fps: float = 30, baked: dict | None = None, where: dict | None = None) -> dict:
    node = {"id": item["id"], "type": item["type"],
            "props": {p.name: item.get(p.name, p.default) for p in F.FIELDS[item["type"]]
                       if p.name not in python_only(item["type"])}}
    if "loop" in node["props"]:         # an older document's on/off switch reaches the engine as a mode
        node["props"]["loop"] = looping.mode_of(node["props"]["loop"])
    anim = {**_anim(item, (where or {}).get("until", 0.0)), **(baked or {}).get(item["id"], {})}
    anim = fill_paint.engine_anim(item, anim)      # a gradient fill goes as its effect (below)
    if anim:
        node["anim"] = anim
    fill_paint.engine_props(item, node["props"])
    if item["type"] in fill_fields.OWNERS and fill_paint.kind_of(item) == "painted":    # a painting: its drawings as the fill picture
        node["fillFrames"] = painted_fill.of(item, fps, where)
    if item["type"] in media.TYPES and (where or {}).get("folder") is not None and item.get("src"):
        node["props"]["src"] = str(media.file(where["folder"], item))   # stored relative to the project: the file to open
    for key in ("effects", "masks", "layers") + (("stops",) if item["type"] == "gradient" else ()):   # a layer's own stops go as its fill (below)
        if item.get(key):
            node[key] = [_node(child, fps, baked, where) for child in item[key] if not child.get("hidden")]   # hidden: not drawn
    fill = fill_paint.lower(item) if item["type"] in fill_fields.OWNERS else None
    if fill is not None:                # a gradient fill: the engine's gradient effect, first; it takes the place of any other
        node["effects"] = [_node(fill, fps, None, where)] + [e for e in node.get("effects", []) if e["type"] != "gradient"]
    back = group_bg.node(item, node, lambda f: _keys(item, f, (where or {}).get("until", 0.0)), _engine_props) if item["type"] == "group" else None
    if back is not None:                # the group's own background: its backmost layer (group_bg.py)
        node["layers"] = [back] + node.get("layers", [])
    if item["type"] == "rig":           # bones, iks and binds are nodes of their own (RIG.md § Scene description)
        node["rig"] = [_node(c, fps, baked, where) for key in ("bones", "iks", "binds") for c in item.get(key, [])]
    if item["type"] == "drawing":       # the painting kit makes each drawing's picture once; the engine only reads it
        node["frames"] = _pictures(item, fps, where)
    elif item.get("frames"):            # paint on an element: drawn over it, stretched over its box (paint_fields.py)
        node["paint"] = {"frames": _pictures(item, fps, where), "inside": item.get("paintInside", True)}
    if item["type"] == "video":         # decoded once (video.py); the engine picks the frame by the time
        node["frames"] = video.frames({**node["props"], "id": item["id"]}, fps)
    if item["type"] == "render3d":      # the 3D item's render, from the project (render3d.py)
        node = _render3d(node, item, fps, where or {})
    if item["type"] == "text" and (font := missing_font.trouble(item)):
        node = _font_stand_in(node, item, font, where or {})
    return node


def _font_stand_in(node: dict, item: dict, font: str, where: dict) -> dict:
    """A text whose font is missing is, in looks, on the screen and in part renders (`span` given), its box with a dashed
    red edge and the font's name, with a warning in the scene's `warnings`; a whole-film export is refused in `describe`."""
    if where.get("span") is None:
        where.setdefault("missing_fonts", {})[item["id"]] = font
        return node
    where.setdefault("warnings", []).append(f'{item["id"]} shows a placeholder: the font "{font}" is not on this computer')
    return missing_font.stand_in(node, font, _engine_props)


def _pictures(item: dict, fps: float, where: dict | None) -> list[dict]:
    """The drawings that can show (the Draw each frame rule, drawing.py), each as its picture; a looping drawing's
    run repeated to the layer's end (or the composition's)."""
    until = min(item.get("end", retime.END_OF_COMP), (where or {}).get("until", 0.0) or 60.0)
    later = (where or {}).get("later")
    return [{"at": n, "src": str(drawing.picture(item, f, later))} for n, f in drawing.repeats(item, math.ceil(until * fps))]


def _render3d(node: dict, item: dict, fps: float, where: dict) -> dict:
    """The render's frames. A layer whose item isn't rendered yet is, in looks and part renders (`span` given), a
    labelled placeholder card at its own box, with a warning in the scene's `warnings`; a whole-film export fails loudly."""
    try:
        return render3d.node(node, item, fps, where.get("folder"))
    except render3d.NotRendered as e:
        if where.get("span") is None:
            raise
        span = where["span"]
        if item.get("start", 0.0) <= span[1] and item.get("end", retime.END_OF_COMP) > span[0]:       # only where it shows
            where.setdefault("warnings", []).append(f'{item["id"]} shows a placeholder: 3D item {item.get("item", "")} is not rendered yet')
        return _placeholder(node, item, e.subject)


def _engine_props(type_: str, given: dict) -> dict:
    """A node's props as the engine takes them: every field the engine knows (default unless given), none of the
    document-only ones (timing from markers, ids …)."""
    props = {p.name: given.get(p.name, p.default) for p in F.FIELDS[type_] if p.name not in python_only(type_)}
    if props.get("fillUnder", "") is None:       # "no colour under it" goes as see-through (fill_paint.NO_COLOUR), as _node sends it
        props["fillUnder"] = fill_paint.NO_COLOUR
    return props


def _placeholder(node: dict, item: dict, name: str) -> dict:
    """A flat grey card with a thin border and a centred label, from ordinary nodes, in the layer's box, transform and timing."""
    props = node["props"]
    w, h = props["w"], props["h"]
    group = _engine_props("group", props)
    anim = {k: v for k, v in node.get("anim", {}).items() if k in group}
    card = {"id": f'{item["id"]}.card', "type": "shape", "props": _engine_props("shape", {
        "shape": "rect", "w": w, "h": h, "x": w / 2, "y": h / 2, "fill": "#808080", "stroke": True, "strokeColor": "#d0d0d0",
        "strokeWidth": 2.0})}
    label = {"id": f'{item["id"]}.label', "type": "text", "props": _engine_props("text", {
        "body": f"3D: {name} — not rendered yet", "size": max(12.0, min(h * 0.08, w * 0.05, 64.0)), "weight": 500.0,
        "color": "#ffffff", "boxWidth": w * 0.9, "x": w / 2, "y": h / 2})}
    return {"id": node["id"], "type": "group", "props": group, **({"anim": anim} if anim else {}), "layers": [card, label]}


def describe(doc_data: dict, comp_id: str | None = None, markers: dict | None = None, folder=None,
             span: tuple[float, float] | None = None, later: list | None = None) -> dict:
    """The scene description of one composition (the first when not named). `markers`: the project's shared
    markers {name: seconds} (rostrum_core.markers.times(folder)), for expressions' marker("…"). `folder`: the
    project folder, where 3D render layers find their item's renders. `span`: (first, last) seconds that will be drawn,
    when not the whole composition (looks, a part of a video): a 3D layer not rendered yet is then a placeholder
    (the scene's `warnings` name it); with no span (a whole-film export) it is refused. `later` (the screen): paint
    pictures not made yet are listed there instead of made (drawing.picture), with stand-ins in the scene; the screen
    makes them off its thread, then describes again and draws: the same pictures export makes at once."""
    comps = doc_data.get("comps", [])
    if not comps:
        raise ValueError("the document has no composition yet (comp.add)")
    library.use_project(folder)                      # strokes may name the project's own tip / paper pictures
    comp = comps[0] if comp_id is None else next((c for c in comps if c["id"] == comp_id), None)
    if comp is None:
        raise ValueError(f'no composition "{comp_id}"; there are: {", ".join(c["id"] for c in comps)}')
    fps = comp.get("fps", F.defaults("comp")["fps"])
    comp = retime.timed(comp, markers, fps)          # layers timed from a marker: every time in comp seconds from here
    baked = exprbake.bake(comp, fps, markers, lambda: project_sound.beats(folder, comp.get("soundtrack", ""), comp.get("duration", 5.0)))
    for item_id, fields in layoutbake.bake(comp, fps, baked).items():
        baked.setdefault(item_id, {}).update(fields)
    where = {"folder": folder, "markers": markers, "span": span, "until": comp.get("duration", F.defaults("comp")["duration"]),
             "later": later, "paintings": {p["id"]: p for p in doc_data.get("paintings", [])}}
    node = _node(comp, fps, baked, where)
    if where.get("missing_fonts"):       # a whole-film export never writes a file with a stand-in in it
        raise RostrumError(codes.RENDER_FAILED, "export", "the texts " + ", ".join(where["missing_fonts"]),
                           "use a font this computer lacks: " + missing_font.refusal(where["missing_fonts"]),
                           hint="Pick another font for them (font.replace), or install it.")
    node["layers"] = sorted(node.get("layers", []), key=lambda n: n["type"] != "camera")   # the frame first (the contract)
    swap.apply(node, exprbake.items_of(comp), comp.get("duration", F.defaults("comp")["duration"]), fps)
    stepped.apply(node, exprbake.items_of(comp), comp.get("duration", F.defaults("comp")["duration"]), fps)
    return {"format": FORMAT, "version": VERSION, "comp": node, **({"warnings": where["warnings"]} if where.get("warnings") else {})}

