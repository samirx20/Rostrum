"""The scene description: what the Python layer sends the engine (ENGINE_CONTRACT.md). One composition, every
item's still values with defaults filled in, and the keys of its animated fields; the engine evaluates them per
frame (the evaluation's reference is evaluate.py). A field with an expression (exprbake.py) is sent as linear keys,
one per frame, in place of its own keys; so is a field an animation layer moves (layerbake.py), the stack over its
keys or expression, and a field an auto layout sets (layoutbake.py), over all of it. A stepped
item's ("on twos", stepped.py) animated fields are then sent as hold keys every n frames. A swap set (swap.py) is
sent as a plain group whose children's opacity shows one at a time; a 3D render layer (render3d.py) is
sent as a video layer over the render's frames. A layer timed from a shared marker (retime.py) has its times
made composition times first. The layout and swap fields themselves stay on
the Python side (`python_only`): the engine never sees them. Rigs, long IK chains included, are the engine's.
"""
from __future__ import annotations

import math
from functools import lru_cache

from . import drawing, drawing_loop, group_bg, missing_font, exprbake, fields as F, fill_fields, fill_paint, layerbake, layoutbake, looping, media, paint_fields, painted_fill, project_sound, render3d, retime, stepped, swap, video, write_on
from .frame import fields as _frame_fields
from .layout_fields import py_only
from rostrum_core import RostrumError, plugin_parts
from rostrum_core.errors import codes
from rostrum_core.keys import after, animated, keys_of, springs
from rostrum_paint import library

FORMAT, VERSION = "rostrum-2d-scene", 3      # 2: the scene's frame (FRAME.md) in place of cameras; 3: picture / painted fill per use


KEY_FIELDS = ("t", "v", "c", "d", "ease", "x1", "y1", "x2", "y2", "stiffness", "damping", "out", "in")   # out / in: spatial handles


@lru_cache(maxsize=None)
def python_only(kind: str) -> frozenset[str]:
    """The fields of an item type the engine never sees: auto layout's, stepped timing's and swap sets' (all
    applied here), the scene's soundtrack (Sound's engine plays it, not 2D's) and work area (the screen's) and a text's style link (its values are
    already on the text: text_styles.py). Fixed per type: worked out once (a scene asks for it per field)."""
    return frozenset(py_only(kind) | {stepped.FIELD, retime.FIELD, retime.END, "locked", "hidden", "eachFrame", "newHold", "soundtrack", "textStyle", "workStart", "workEnd"} | ({"loop", *drawing_loop.FIELDS} if kind == "drawing" else set()) | (group_bg.NAMES if kind == "group" else set()) | swap.PY_ONLY.get(kind, set())
            | paint_fields.NAMES | fill_fields.NAMES | _frame_fields.NOT_IN_ENGINE_YET.get(kind, set()))


def _key(key: dict) -> dict:
    """A key as the engine reads it: a spring written as bounce / speed goes as its stiffness / damping (springs)."""
    out = {k: key[k] for k in KEY_FIELDS if k in key}
    if key.get("ease") == "spring" and ("bounce" in key or "speed" in key):
        out["stiffness"], out["damping"] = springs.physics_of(key)
    return out


def _anim(item: dict, until: float) -> dict:
    """Each animated field's keys; a last key's "after the last key" goes written out as plain keys up to `until`, the
    composition's end (rostrum_core.keys.after: the engine reads keys only)."""
    anim = {prop: _keys(item, prop, until) for prop in sorted(animated(item)) if prop not in python_only(item["type"])}
    return {prop: keys for prop, keys in anim.items() if keys}   # a field keyed only on a layer: its Base is still


def _keys(item: dict, prop: str, until: float) -> list[dict]:
    """One field's keys as the engine reads them (empty when it isn't animated)."""
    return [_key(key) for key in after.extend(keys_of(item, prop), until)] if prop in animated(item) else []


def _node(item: dict, fps: float = 30, baked: dict | None = None, where: dict | None = None, n: int | None = None,
          vis: tuple | None = None) -> dict:
    """The item's engine node, whole and final (never changed after: the screen keeps it, scene_keep.py). `n`: its
    group's stepped timing (None at the composition); `vis`: its swap set's shown-or-not per frame (swap.gates). The
    document's own children are made through `where["make"]` (this function; the screen's keeper there)."""
    where = {} if where is None else where
    until, make, step = where.get("until", 0.0), where.get("make", _node), stepped.step_of(item, n)
    node = {"id": item["id"], "type": item["type"],
            "props": {p.name: item.get(p.name, p.default) for p in F.FIELDS[item["type"]]
                       if p.name not in python_only(item["type"])}}
    if "loop" in node["props"]:         # an older document's on/off switch reaches the engine as a mode
        node["props"]["loop"] = looping.mode_of(node["props"]["loop"])
    anim = {**_anim(item, until), **(baked or {}).get(item["id"], {})}
    if "boxWidth" in anim:      # a layout's wrap width: a still field for the engine, so the widest it takes
        widths = [k["v"] for k in anim.pop("boxWidth") if k["v"] > 0]
        node["props"]["boxWidth"] = max(widths) if widths else node["props"].get("boxWidth", 0)
    anim = fill_paint.engine_anim(item, anim)      # a gradient fill goes as its effect (below)
    if anim:
        node["anim"] = anim
    fill_paint.engine_props(item, node["props"])
    if item["type"] in fill_fields.OWNERS and fill_paint.kind_of(item) == "painted":    # a painting: its drawings as the fill picture
        node["fillFrames"] = painted_fill.of(item, fps, where)
    if item["type"] in media.TYPES and where.get("folder") is not None and item.get("src"):
        node["props"]["src"] = str(media.file(where["folder"], item))   # stored relative to the project: the file to open
    shown = [c for c in item.get("layers", []) if not c.get("hidden")]                 # hidden: not drawn
    back_on = item["type"] == "group" and bool(item.get("background"))
    gates = swap.gates(item, len(shown) + back_on, until, fps)     # a swap set: one child at a time (its background first)
    for key in ("effects", "masks", "layers") + (("stops",) if item["type"] == "gradient" else ()):   # a layer's own stops go as its fill (below)
        if item.get(key):               # stops are never stepped (1); a swap set's layers each get their vis
            kids = shown if key == "layers" else [c for c in item[key] if not c.get("hidden")]
            node[key] = [make(c, fps, baked, where, 1 if key == "stops" else step,
                              gates[i + back_on] if gates and key == "layers" else None) for i, c in enumerate(kids)]
    fill = fill_paint.lower(item) if item["type"] in fill_fields.OWNERS else None
    if fill is not None:                # a gradient fill: the engine's gradient effect, first; it takes the place of any other
        node["effects"] = [_node(fill, fps, None, where, step)] + [e for e in node.get("effects", []) if e["type"] != "gradient"]
    back = group_bg.node(item, node, lambda f: _keys(item, f, until), _engine_props) if back_on else None
    if back is not None:                # the group's own background: its backmost layer (group_bg.py)
        node["layers"] = [_posed(back, step, gates[0] if gates else None, fps, until)] + node.get("layers", [])
    if item["type"] == "rig":           # bones, iks and binds are nodes of their own (RIG.md § Scene description)
        node["rig"] = [make(c, fps, baked, where, step, None) for key in ("bones", "iks", "binds") for c in item.get(key, [])]
    if item["type"] == "drawing":       # the painting kit makes each drawing's picture once; the engine only reads it
        node["frames"] = _pictures(item, fps, where)
        drawing_loop.step(node, item, drawing.cycle(item), drawing.canvas_size(item), fps, until)   # a cycle's steps
    elif item.get("frames"):            # paint on an element: drawn over it, stretched over its box (paint_fields.py)
        node["paint"] = {"frames": _pictures(item, fps, where), "inside": item.get("paintInside", True)}
    if item["type"] == "video":         # decoded once (video.py); the engine picks the frame by the time
        node["frames"] = video.frames({**node["props"], "id": item["id"]}, fps)
    if item["type"] == "render3d":      # the 3D item's render, from the project (render3d.py)
        node = _render3d(node, item, fps, where)
    if item["type"] == "text" and (font := missing_font.trouble(item)):
        node = _font_stand_in(node, item, font, where)
    return _posed(node, step, vis, fps, until)


def _posed(node: dict, step: int, vis: tuple | None, fps: float, until: float) -> dict:
    """A node being built, shown by its swap set (vis) and then held every `step` frames (stepped.py), in that order."""
    if vis is not None:
        swap.gate(node, vis, fps)
    if step > 1 and node.get("anim"):
        node["anim"] = stepped.held(node["anim"], step, until, fps)
    return node


def _font_stand_in(node: dict, item: dict, font: str, where: dict) -> dict:
    """A text whose font is missing is, in looks, on the screen and in part renders (`span` given), its box with a dashed
    red edge and the font's name, with a warning in the scene's `warnings`; a whole-film export is refused in `describe`."""
    if where.get("span") is None:
        where.setdefault("missing_fonts", {})[item["id"]] = font
        return node
    where.setdefault("warnings", []).append(f'{item["id"]} shows a placeholder: the font "{font}" is not on this computer')
    return missing_font.stand_in(node, font, _engine_props)


SPARE = 2       # frames either side of a span whose drawings are sent too (a motion blur's samples reach past the frame)
REACH = ("trail", "smear")      # effects that draw a layer at other times than the frame (motion/fields.py)


def _spare(comp: dict, doc_data: dict | None = None) -> int:
    """How many frames either side of a span reach into it: SPARE with motion blur (the composition's shutter) or a
    trail or smear anywhere, else none. A look at one moment of a painted piece made a Drawn so far picture for 5 frames
    of each drawing, 4 of them never drawn (production round: 6.8 s of a cold look, 3.2 s without)."""
    if comp.get("shutter", 0.0) or any(c.get("shutter", 0.0) for c in (doc_data or {}).get("comps", [])):
        return SPARE                     # (any composition's: one placed inside this one blurs its own frames)

    def reaches(item: dict) -> bool:
        return any(e.get("type") in REACH for e in item.get("effects", [])) or any(reaches(c) for c in item.get("layers", []))
    return SPARE if reaches(comp) else 0


def _pictures(item: dict, fps: float, where: dict | None) -> list[dict]:
    """The drawings that can show (the Draw each frame rule, drawing.py), each as its picture; a looping drawing's
    run repeated to the layer's end (or the composition's). A drawing layer's pictures are cropped to their ink; paint
    on an element covers its whole box. Drawn so far under 100 % (or keyed): a picture per frame it changes (write_on.py)."""
    until = min(item.get("end", retime.END_OF_COMP), (where or {}).get("until", 0.0) or 60.0)
    later, span = (where or {}).get("later"), (where or {}).get("span")
    run = drawing.repeats(item, math.ceil(until * fps))
    first, last = 0, math.ceil(until * fps)
    if span is not None:                # a look or a part: only the drawings showing then (motion blur's reach spared)
        spare = where.get("spare", SPARE)
        first, last = math.floor(span[0] * fps) - spare, math.ceil(span[1] * fps) + spare
        run = drawing.within(run, first, last) or run[:1]
    if item["type"] == "drawing":       # a drawing's picture holds only its ink, with where it goes (`crop`)
        full = lambda f: drawing.inked(item, f, later)                                  # noqa: E731
    else:
        full = lambda f: {"src": str(drawing.picture(item, f, later))}                  # noqa: E731
    if item.get(paint_fields.DRAWN, 1.0) >= 1 and not keys_of(item, paint_fields.DRAWN):
        return [{"at": n, **full(f)} for n, f in run]
    return write_on.entries(item, run, fps, first, last, drawing.canvas_size(item), full, later,   # Drawn so far
                            (where or {}).get("frames"))


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
             span: tuple[float, float] | None = None, later: list | None = None, frames: list[int] | None = None,
             progress=None, stopped=None) -> dict:
    """The scene description of one composition (the first when not named). `markers`: the project's shared
    markers {name: seconds} (rostrum_core.markers.times(folder)), for expressions' marker("…"). `folder`: the
    project folder, where 3D render layers find their item's renders. `span`: (first, last) seconds that will be drawn,
    when not the whole composition (looks, a part of a video): a 3D layer not rendered yet is then a placeholder
    (the scene's `warnings` name it); with no span (a whole-film export) it is refused. `later` (the screen): paint
    pictures not made yet are listed there instead of made (drawing.picture), with stand-ins in the scene; the screen
    makes them off its thread, then describes again and draws: the same pictures export makes at once. The screen
    describes through scene_keep.Keeper: the same description, reusing the nodes a change didn't touch. `frames`
    (with `span`): the only frame numbers that will be drawn (a contact sheet's tiles): Drawn so far pictures are made
    for those (and the motion blur's reach round them), not for every frame between the first and the last.
    `progress(done, total)` / `stopped()`: the pictures made first (drawing.make_all), for an export's job."""
    if later is None:       # the paint pictures not made yet are made first, side by side (drawing.make_all)
        jobs: list = []
        comp, fps, baked, where = prepare(doc_data, comp_id, markers, folder, span, jobs, frames=frames)
        node = _node(comp, fps, baked, where)
        if not jobs:        # every picture was made already: that description is the final one
            return finish(node, where)
        drawing.make_all(jobs, progress, stopped)
    comp, fps, baked, where = prepare(doc_data, comp_id, markers, folder, span, later, frames=frames)
    return finish(_node(comp, fps, baked, where), where)


def prepare(doc_data: dict, comp_id, markers, folder, span, later, timed_memo: dict | None = None,
            frames: list[int] | None = None) -> tuple:
    """(the composition in composition seconds, its fps, the baked expression / layout keys, `where`): what every
    node is made from. `timed_memo`: retime.timed's, kept by scene_keep.Keeper. A plugin's items are left out here,
    once for every path (rostrum_core.plugin_parts: kept in the file, never drawn)."""
    from .kind import LISTS
    doc_data = plugin_parts.engine_tree(doc_data, LISTS)
    comps = doc_data.get("comps", [])
    if not comps:
        raise ValueError("the document has no composition yet (comp.add)")
    library.use_project(folder)                      # strokes may name the project's own tip / paper pictures
    comp = comps[0] if comp_id is None else next((c for c in comps if c["id"] == comp_id), None)
    if comp is None:
        raise ValueError(f'no composition "{comp_id}"; there are: {", ".join(c["id"] for c in comps)}')
    fps = comp.get("fps", F.defaults("comp")["fps"])
    comp = retime.timed(comp, markers, fps, timed_memo)   # layers timed from a marker: every time in comp seconds from here
    baked = exprbake.bake(comp, fps, markers, lambda: project_sound.beats(folder, comp.get("soundtrack", ""), comp.get("duration", 5.0)))
    for item_id, fields in layerbake.bake(doc_data, comp, fps, baked).items():    # animation layers over the Base
        baked.setdefault(item_id, {}).update(fields)
    for item_id, fields in layoutbake.bake(comp, fps, baked).items():
        baked.setdefault(item_id, {}).update(fields)
    where = {"folder": folder, "markers": markers, "span": span, "until": comp.get("duration", F.defaults("comp")["duration"]),
             "later": later, "paintings": {p["id"]: p for p in doc_data.get("paintings", [])}, "spare": _spare(comp, doc_data)}
    if frames is not None and span is not None:
        where["frames"] = {n + k for n in frames for k in range(-where["spare"], where["spare"] + 1)}
    return comp, fps, baked, where


def finish(node: dict, where: dict) -> dict:
    """The description around the composition's node (a new node each call: its layers are put in order here)."""
    if where.get("missing_fonts"):       # a whole-film export never writes a file with a stand-in in it
        raise RostrumError(codes.RENDER_FAILED, "export", "the texts " + ", ".join(where["missing_fonts"]),
                           "use a font this computer lacks: " + missing_font.refusal(where["missing_fonts"]),
                           hint="Pick another font for them (font.replace), or install it.")
    node["layers"] = sorted(node.get("layers", []), key=lambda n: n["type"] != "camera")   # the frame first (the contract)
    return {"format": FORMAT, "version": VERSION, "comp": node, **({"warnings": where["warnings"]} if where.get("warnings") else {})}
