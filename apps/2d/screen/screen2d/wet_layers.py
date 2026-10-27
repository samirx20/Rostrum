"""Wet ink in its layer's place: while a stroke is drawn on a layer with layers above it, the screen shows in each wet
box the world drawn under the stroke (`under`, opaque), the wet ink, then the layers above the layer alone (`above`, on a
see-through background): the frame that will land, the layers above covering the stroke as they will (a live smear
showed over every layer until it landed: critic r12). The pictures a stroke asks of the canvas's engine (`asks`):
- "erase": the world without the layer's paint, the layers above in it (the eraser's ink is its coverage, and erasing
  is linear in the paint's alpha: wet_ink.py), no split;
- "smear": a smudge's pictures hold the layer's paint with the smear in it, so `under` is the world below the layer;
- "ink": normal ink lies on the layer's paint: `under` is the world up to the layer, its paint in it; nothing is asked
  when no layer is above (the ink lies on the world shown, which is then exact).
Layers draw in their order (the last on top); a group's background is its first layer. No Qt.
"""
from __future__ import annotations


def _path(node: dict, layer_id: str) -> list[int] | None:
    """The indexes through each node's "layers" down to `layer_id` ([] for the node itself), or None."""
    if node.get("id") == layer_id:
        return []
    for i, kid in enumerate(node.get("layers") or []):
        got = _path(kid, layer_id)
        if got is not None:
            return [i, *got]
    return None


def _stripped(node: dict, fill: bool) -> dict:
    """The layer with its paint left out (a drawing draws nothing; an element still draws its own look), or with `fill`
    its painted fill's painting (the colour under it stays)."""
    if fill:
        return {**{k: v for k, v in node.items() if k != "fillFrames"}, "props": {**node["props"], "fillPicture": ""}}
    out = {k: v for k, v in node.items() if k != "paint"}
    if node["type"] == "drawing":
        out["frames"] = []
    return out


def _under(node: dict, path: list[int], last) -> dict:
    """`node` with the layer at `path` replaced by `last(layer)` and every layer after it left out."""
    if not path:
        return last(node)
    kids, i = node["layers"], path[0]
    return {**node, "layers": kids[:i] + [_under(kids[i], path[1:], last)]}


def _above(node: dict, path: list[int]) -> tuple[dict, bool]:
    """`node` with only what draws after the layer at `path` (the nodes on the way kept, their earlier layers left
    out), and whether anything is left."""
    kids, i = node["layers"], path[0]
    after = kids[i + 1:]
    if len(path) == 1:
        return {**node, "layers": after}, bool(after)
    inner, some = _above(kids[i], path[1:])
    return {**node, "layers": [inner, *after]}, some or bool(after)


def has_above(scene: dict, layer_id: str) -> bool:
    path = _path(scene["comp"], layer_id)
    return bool(path) and _above(scene["comp"], path)[1]


def asks(scene: dict, layer_id: str, fill: bool, kind: str) -> dict[str, dict] | None:
    """{"under": scene[, "above": scene]} to draw for a stroke of `kind` on `layer_id` ({} : nothing; None: the layer
    isn't in the scene). Only the nodes on the way are copied (the scene is shared)."""
    comp = scene["comp"]
    path = _path(comp, layer_id)
    if path is None:
        return None
    if kind == "erase":
        return {"under": {**scene, "comp": _under_all(comp, path, lambda n: _stripped(n, fill))}}
    above, some = _above(comp, path) if path else (None, False)
    if kind == "ink" and not some:
        return {}
    out = {"under": {**scene, "comp": _under(comp, path, (lambda n: _stripped(n, fill)) if kind == "smear" else (lambda n: n))}}
    if some:
        out["above"] = {**scene, "comp": {**above, "props": {**above["props"], "background": "#00000000"}}}
    return out


def _under_all(node: dict, path: list[int], last) -> dict:
    """`node` with the layer at `path` replaced by `last(layer)`, every other layer kept."""
    if not path:
        return last(node)
    kids, i = node["layers"], path[0]
    return {**node, "layers": kids[:i] + [_under_all(kids[i], path[1:], last)] + kids[i + 1:]}


def kind_of(ink) -> str:
    """What a stroke's wet ink does, for `asks` (wet_ink.WetInk)."""
    return "erase" if ink.erasing else "smear" if ink.smears else "ink"


def draw(frames, scenes: dict[str, dict], t: float, samples, rect: dict, done) -> None:
    """Each of `scenes` (asks) drawn by the canvas's engine at world rectangle `rect` (wet.reveal_rect), off the screen's
    thread; `done({part: (straight RGBA8, (x, y))}, error)` once, on the engine's worker, when all came or one failed."""
    got, parts = {}, list(scenes)
    if not parts:
        return done({}, None)

    def came(part, px, error):
        if error is not None:
            if not got.get("failed"):
                got["failed"] = True
                done(None, error)
            return
        if got.get("failed"):
            return
        got[part] = (px, (rect["x"], rect["y"]))
        if len(got) == len(parts):
            done(got, None)
    for part in parts:
        frames.still(scenes[part], t, samples, lambda px, e, part=part: came(part, px, e), rect)
