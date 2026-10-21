"""Image layers → Lottie image layers with the file embedded (a base64 data URI asset, `e: 1`).

A Lottie image layer is the picture at its own px. Our `fit` (cover, contain, stretch) becomes the layer's scale and
anchor; the box (corner radius, and the part cover cuts off) becomes a mask in the picture's own px.
"""
from __future__ import annotations

import base64
from pathlib import Path

from PIL import Image

from .. import pathdata
from .lottie_layer import common, transform
from .lottie_props import Ctx, frozen
from .lottie_shapes import shape_value

MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}


def _asset(src: str, assets: list[dict]) -> tuple[str, int, int]:
    path = Path(src)
    if not path.is_file():
        raise FileNotFoundError(f"image not found: {src}")
    if path.suffix.lower() not in MIME:
        raise ValueError(f"image {src}: Lottie embeds png, jpeg, webp or gif only")
    for a in assets:
        if a.get("nm") == str(path):
            return a["id"], a["w"], a["h"]
    with Image.open(path) as im:
        iw, ih = im.size
    uri = f"data:{MIME[path.suffix.lower()]};base64," + base64.b64encode(path.read_bytes()).decode("ascii")
    aid = f"image_{len(assets)}"
    assets.append({"id": aid, "w": iw, "h": ih, "u": "", "p": uri, "e": 1, "nm": str(path)})
    return aid, iw, ih


def image_layer(node: dict, ctx: Ctx, assets: list[dict], ind: int) -> dict:
    """One image layer (its size and fit can't be keyed: they are held at their first values, and the report says so)."""
    props = frozen(node, ["w", "h", "fit", "radius", "src"], ctx, "an image's fit and box can't be keyed in Lottie")
    node = {**node, "props": props, "anim": {k: v for k, v in node.get("anim", {}).items() if k not in ("w", "h", "radius")}}
    aid, iw, ih = _asset(props["src"], assets)
    w, h, fit, r = props["w"], props["h"], props["fit"], props["radius"]
    if fit == "stretch":
        sfx, sfy = w / iw, h / ih
    else:
        sfx = sfy = (max if fit == "cover" else min)(w / iw, h / ih)
    layer = common(node, ctx, 2, ind)
    layer["ks"] = transform(node, ctx, fit=(iw, ih, sfx, sfy))
    layer["refId"] = aid
    if r > 0 or fit == "cover":                                 # the box, in the picture's px, cuts the layer
        bw, bh = w / sfx, h / sfy
        d = pathdata.write(pathdata.transformed(pathdata.commands(pathdata.rect(bw, bh, r / sfx)),
                                                lambda x, y: (x + iw / 2 - bw / 2, y + ih / 2 - bh / 2)))
        layer["hasMask"] = True
        layer["masksProperties"] = [*layer.get("masksProperties", []),
                                    {"nm": "box", "inv": False, "mode": "i" if layer.get("masksProperties") else "a",
                                     "o": {"a": 0, "k": 100}, "x": {"a": 0, "k": 0}, "pt": {"a": 0, "k": shape_value(d)}}]
    return layer
