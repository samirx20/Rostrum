"""PSD → import tree (psd-tools, MIT). Pixel layers become image layers, groups become groups. Text, shape, smart-object
and adjustment layers come in as their rendered pixels (the report says so); layer masks and effects are baked in.
"""
from __future__ import annotations

from pathlib import Path

from psd_tools import PSDImage
from psd_tools.constants import BlendMode as B

# Photoshop blend mode → ours; anything else is drawn normal and reported.
BLEND = {B.NORMAL: "normal", B.PASS_THROUGH: "normal", B.SCREEN: "screen", B.LINEAR_DODGE: "add",
         B.MULTIPLY: "multiply", B.OVERLAY: "overlay", B.SOFT_LIGHT: "soft-light"}
_RENDERED = {"type": "text", "shape": "shape", "smartobject": "smart object", "adjustment": "adjustment",
             "fill": "fill", "solidcolorfill": "fill", "gradientfill": "fill", "patternfill": "fill"}


def psd_tree(path) -> dict:
    """Read a .psd → the import tree (bottom layer first)."""
    path = Path(path)
    psd = PSDImage.open(path)
    report: list[str] = []
    layers = _walk(psd, report)
    if not layers:
        raise ValueError(f"{path.name} has no layers with pixels")
    return {"name": path.name, "width": psd.width, "height": psd.height, "layers": layers, "report": report}


def _walk(parent, report: list) -> list[dict]:
    out = []
    for layer in parent:                                   # psd-tools lists bottom first
        node = _group(layer, report) if layer.is_group() else _pixels(layer, report)
        if node is None:
            continue
        opacity = layer.opacity / 255 * (layer.fill_opacity / 255 if not layer.is_group() else 1.0)
        if not layer.visible:
            report.append(f"layer '{layer.name}' is hidden in the PSD; imported with opacity 0")
            opacity = 0.0
        blend = BLEND.get(layer.blend_mode)
        if blend is None:
            report.append(f"layer '{layer.name}': blend mode {layer.blend_mode.name.lower().replace('_', ' ')} "
                          "is not in the app; drawn normal")
            blend = "normal"
        node["props"].update({"opacity": round(opacity, 4), "blend": blend})
        out.append(node)
    return out


def _group(layer, report: list) -> dict | None:
    kids = _walk(layer, report)
    if not kids:
        report.append(f"group '{layer.name}' has no layers with pixels; left out")
        return None
    return {"type": "group", "name": layer.name, "props": {}, "layers": kids}


def _pixels(layer, report: list) -> dict | None:
    l, t, r, b = layer.bbox
    if r <= l or b <= t:
        report.append(f"layer '{layer.name}' is empty; left out")
        return None
    plain = layer.kind == "pixel" and layer.has_pixels() and not layer.has_mask() and not layer.has_effects()
    try:
        img = layer.topil() if plain else layer.composite()
    except Exception as e:                                   # psd-tools raises many kinds; say which layer
        raise ValueError(f"layer '{layer.name}': pixels could not be read ({e})") from e
    if img is None:
        report.append(f"layer '{layer.name}' has no pixels; left out")
        return None
    what = _RENDERED.get(layer.kind)
    if what:
        report.append(f"{what} layer '{layer.name}' came in as its pixels (not editable)")
    elif not plain:
        report.append(f"layer '{layer.name}': its mask / effects are baked into the pixels")
    img = img.convert("RGBA")
    return {"type": "image", "name": layer.name, "box": [l, t, img.width, img.height], "image": img,
            "props": {"fit": "stretch"}}
