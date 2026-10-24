"""PSD → import tree (psd-tools, MIT). What comes in as the real thing:
- pixel layers → image layers, groups → groups, blend modes and opacity;
- text layers → text items when their font is in the app and the layer is one plain style (psd_text.py);
- shape layers → path items with solid fill / outline (psd_shape.py);
- layer masks and vector masks → masks, or a track matte layer when freer than a box / ellipse (psd_mask.py).
Smart objects, adjustment layers, fills and layers with effects come in as their rendered pixels (effects and masks baked);
the report lists each one by name. A layer that can't be live (font missing, gradient fill …) keeps its pixels, and says why.
"""
from __future__ import annotations

from pathlib import Path

from psd_tools import PSDImage
from psd_tools.constants import BlendMode as B

from .. import blends
from .psd_mask import masks_for
from .psd_shape import shape_node
from .psd_text import text_node
from .tree import Report, _boxes

# Photoshop blend mode → ours; anything else is drawn normal and reported.
BLEND = {B[k]: v for k, v in blends.DESIGN_APPS.items()}     # the one list (blends.txt), by Photoshop's names
_BAKED = {"smartobject": "smart object", "adjustment": "adjustment", "fill": "fill", "solidcolorfill": "fill",
          "gradientfill": "fill", "patternfill": "fill"}      # kinds that are always their pixels
_LIVE = ("type", "shape")                                      # kinds that can become text / path items


def psd_tree(path, fonts: set | None = None) -> dict:
    """Read a .psd → the import tree (bottom layer first). `fonts`: the family names the app has (default: its fonts folder)."""
    from .importing import app_fonts                           # the one font lookup (imported late: importing imports this)
    path = Path(path)
    psd = PSDImage.open(path)
    report = Report()
    ctx = {"fonts": app_fonts() if fonts is None else fonts, "size": (psd.width, psd.height)}
    layers = _walk(psd, ctx, report)
    if not layers:
        raise ValueError(f"{path.name} has no layers with pixels")
    return {"name": path.name, "width": psd.width, "height": psd.height, "layers": layers, "report": report, "notes": report.notes()}


def _walk(parent, ctx: dict, report: list) -> list[dict]:
    out = []
    for layer in parent:                                   # psd-tools lists bottom first
        node = _group(layer, ctx, report) if layer.is_group() else _layer(layer, ctx, report)
        if node is None:
            continue
        opacity = layer.opacity / 255 * (layer.fill_opacity / 255 if not layer.is_group() else 1.0)
        if not layer.visible:
            report.hidden.append(layer.name)               # kept hidden (the layer's Hidden switch), not faded to nothing
            node["props"]["hidden"] = True
            if node.get("matte_node"):                     # the engine draws a matte on its own when the layer it serves is hidden
                node["matte_node"]["props"]["hidden"] = True
        blend = BLEND.get(layer.blend_mode)
        if blend is None:
            report.append(f"layer '{layer.name}': blend mode {layer.blend_mode.name.lower().replace('_', ' ')} "
                          "is not in the app; drawn normal")
            blend = "normal"
        node["props"].update({"opacity": round(opacity, 4), "blend": blend})
        matte = node.pop("matte_node", None)
        if matte:
            out.append(matte)                              # the matte layer sits before the layer it masks
        out.append(node)
    return out


def _masked(layer) -> bool:
    return layer.has_mask() or (layer.has_vector_mask() and layer.kind != "shape")   # a shape's vector mask is its outline


def _apply(node: dict, got: dict) -> dict:
    """Put masks_for's answer on the node (real masks, or a matte layer that goes before it)."""
    if got["masks"]:
        node["masks"] = got["masks"]
    if got["matte"]:
        node["matte"] = got["matte"]["name"]
        node["matte_node"] = got["matte"]
        node["props"]["matteMode"] = got["mode"]
    return node


def _group(layer, ctx: dict, report: list) -> dict | None:
    kids = _walk(layer, ctx, report)
    if not kids:
        report.append(f"group '{layer.name}' has no layers with pixels; left out")
        return None
    node = {"type": "group", "name": layer.name, "props": {}, "layers": kids}
    if not _masked(layer):
        return node
    got = masks_for(layer, _boxes(node), ctx["size"], report, group=True)
    return _apply(node, got) if got else node              # (a group's mask that can't be carried is reported; the group shows whole)


def _layer(layer, ctx: dict, report: list) -> dict | None:
    l, t, r, b = layer.bbox
    if r <= l or b <= t:
        report.append(f"layer '{layer.name}' is empty; left out")
        return None
    effects = [type(e).__name__ for e in layer.effects] if layer.has_effects() else []
    if layer.kind in _LIVE and not effects:
        node = (text_node(layer, ctx["fonts"], report) if layer.kind == "type"
                else shape_node(layer, *ctx["size"], report))
        got = masks_for(layer, _boxes(node), ctx["size"], report) if node and _masked(layer) else {}
        if node and got is not None:
            return _apply(node, got) if got else node
    return _pixels(layer, ctx, report, effects)


def _pixels(layer, ctx: dict, report: list, effects: list) -> dict | None:
    l, t, r, b = layer.bbox
    masked = _masked(layer)
    plain = layer.kind == "pixel" and layer.has_pixels() and not effects
    got = masks_for(layer, [l, t, r - l, b - t], ctx["size"], report) if plain and masked else None
    try:
        img = layer.topil() if plain and (got is not None or not masked) else layer.composite()
    except Exception as e:                                   # psd-tools raises many kinds; say which layer
        raise ValueError(f"layer '{layer.name}': pixels could not be read ({e})") from e
    if img is None:
        report.append(f"{_BAKED.get(layer.kind, layer.kind)} layer '{layer.name}' has no pixels of its own; left out")
        return None
    node = {"type": "image", "name": layer.name, "box": [l, t, img.width, img.height], "image": img.convert("RGBA"),
            "props": {"fit": "stretch"}}
    if got is not None:
        return _apply(node, got)
    what = _BAKED.get(layer.kind)                            # text / shape say why themselves (psd_text, psd_shape)
    if what:
        report.append(f"{what} layer '{layer.name}' came in as its pixels (not editable)")
    if effects:
        report.append(f"layer '{layer.name}': effects baked into the pixels: {', '.join(effects)}")
    elif masked and not plain:
        report.append(f"layer '{layer.name}': its mask is baked into the pixels")
    return node
