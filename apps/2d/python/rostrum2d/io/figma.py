"""Figma file → import tree. Fetch with the user's own token (argument or env FIGMA_TOKEN; never stored, never put in
an error or log), then map one frame's nodes to layers. `frame_tree(file_json, …)` is the pure mapping (no network).
BUILT AGAINST THE API DOCS AND A HAND-WRITTEN SAMPLE, NOT TESTED AGAINST THE LIVE API.
"""
from __future__ import annotations

import io
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from PIL import Image

from .. import blends, pathdata as PD
from . import figma_path as FP

API = "https://api.figma.com/v1"
BLEND = blends.DESIGN_APPS        # Figma's blend names → ours (the one list, blends.txt)
GROUPS = {"FRAME", "GROUP", "COMPONENT", "COMPONENT_SET", "INSTANCE", "SECTION"}
SHAPES = {"RECTANGLE": "rect", "ELLIPSE": "ellipse"}


def _get(url: str, token: str | None, raw: bool = False):
    token = token or os.environ.get("FIGMA_TOKEN")
    if not token and url.startswith(API):
        raise ValueError("Figma needs your token: pass token=… or set FIGMA_TOKEN")
    req = urllib.request.Request(url, headers={"X-Figma-Token": token} if url.startswith(API) else {})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
    except urllib.error.HTTPError as e:                  # never echo the request (it carries the token)
        raise ValueError(f"Figma answered {e.code} {e.reason} for {url.split('?')[0]}") from None
    except urllib.error.URLError as e:
        raise ValueError(f"could not reach Figma: {e.reason}") from None
    return body if raw else json.loads(body)


def figma_tree(key: str, frame: str | None = None, token: str | None = None) -> dict:
    """Fetch file `key` and map one frame (by name; the first when None)."""
    file = _get(f"{API}/files/{urllib.parse.quote(key)}?geometry=paths", token)

    def render(node_id: str) -> Image.Image:
        info = _get(f"{API}/images/{urllib.parse.quote(key)}?ids={urllib.parse.quote(node_id)}&format=png&scale=1", token)
        url = (info.get("images") or {}).get(node_id)
        if not url:
            raise ValueError(f"Figma gave no picture for node {node_id}")
        return Image.open(io.BytesIO(_get(url, token, raw=True))).convert("RGBA")

    return frame_tree(file, frame, render)


def _find_frame(file: dict, name: str | None) -> dict:
    frames = [c for page in file["document"]["children"] for c in page.get("children", []) if c["type"] == "FRAME"]
    for f in frames:
        if name is None or f["name"] == name:
            return f
    raise ValueError(f"no frame {name!r} in the file" if name else "the file has no frames")


def frame_tree(file: dict, frame: str | None = None, render=None) -> dict:
    """The mapping: Figma JSON → import tree. `render(node_id)` → PIL image, for nodes with image fills."""
    root, report = _find_frame(file, frame), []
    box = root["absoluteBoundingBox"]
    ox, oy = box["x"], box["y"]
    node = _node(root, ox, oy, report, render)
    return {"name": root["name"], "width": box["width"], "height": box["height"], "report": report,
            "layers": node["layers"] if node["type"] == "group" else [node]}


def _rgba(fill: dict, opacity: float = 1.0) -> str:
    c = fill["color"]
    a = c.get("a", 1.0) * fill.get("opacity", 1.0) * opacity
    return "#%02x%02x%02x%02x" % (*(round(c[k] * 255) for k in "rgb"), round(a * 255))


def _fill(n: dict, key: str, report: list):
    """The first visible solid paint of n[key]; a gradient is reported and its first stop used. None = no paint."""
    for p in n.get(key) or []:
        if p.get("visible", True) is False:
            continue
        if p["type"] == "SOLID":
            return p
        if p["type"].startswith("GRADIENT"):
            report.append(f"'{n['name']}': gradient {key[:-1]} drawn as its first colour")
            return {"color": p["gradientStops"][0]["color"], "opacity": p.get("opacity", 1.0)}
        if p["type"] == "IMAGE":
            return p
    return None


def _node(n: dict, ox: float, oy: float, report: list, render) -> dict | None:
    name, t = n["name"], n["type"]
    bb = n.get("absoluteBoundingBox")
    if bb is None:
        report.append(f"'{name}' ({t}) has no box; left out")
        return None
    box = [bb["x"] - ox, bb["y"] - oy, bb["width"], bb["height"]]
    if n.get("rotation"):
        report.append(f"'{name}': rotation is not carried over")
    if n.get("effects"):
        report.append(f"'{name}': effects (shadows, blurs) are not carried over")
    props, kind = {}, None
    fill = _fill(n, "fills", report)
    image = fill is not None and fill.get("type") == "IMAGE"
    if t in GROUPS:
        kids = []
        if fill is not None and not image:               # a frame's own background becomes a rectangle under its layers
            kids.append(_style({"type": "shape", "name": f"{name} background", "box": box, "props": {"shape": "rect"}},
                               n, fill, report))
        kids += [k for c in n.get("children", []) if (k := _node(c, ox, oy, report, render))]
        if not kids:
            report.append(f"group '{name}' is empty; left out")
            return None
        out = {"type": "group", "name": name, "box": box, "props": {"clip": bool(n.get("clipsContent"))}, "layers": kids}
    elif image:
        if render is None:
            raise ValueError(f"'{name}' has an image fill and no way to render it")
        out = {"type": "image", "name": name, "box": box, "image": render(n["id"]), "props": {"fit": "stretch"}}
    elif t in SHAPES:
        r = float(n.get("cornerRadius", 0))
        if fill is None:                                 # outline only: a shape always has a fill, a path needn't
            d = PD.rect(box[2], box[3], r) if t == "RECTANGLE" else PD.ellipse(box[2], box[3])
            d = PD.write(PD.transformed(PD.commands(d), lambda x, y: (x + box[0], y + box[1])))
            out = _style({"type": "path", "name": name, "box": box, "props": {"d": d}}, n, None, report)
        else:
            props = {"shape": SHAPES[t], "radius": r}
            out = _style({"type": "shape", "name": name, "box": box, "props": props}, n, fill, report)
    elif t == "TEXT":
        out = _text(n, name, box, fill, report)
    else:
        geo = n.get("fillGeometry") or []
        if not geo:
            report.append(f"'{name}' ({t}) has no path geometry; left out")
            return None
        d = FP.to_d([g["path"] for g in geo], bb["x"] - ox, bb["y"] - oy)
        rule = "evenodd" if geo[0].get("windingRule") == "EVENODD" else "nonzero"
        out = _style({"type": "path", "name": name, "box": box, "props": {"d": d, "fillRule": rule}}, n, fill, report)
    return _common(out, n, report)


def _style(out: dict, n: dict, fill, report: list) -> dict:
    p = out["props"]
    if out["type"] == "path":
        p["filled"] = fill is not None
    if fill is not None:
        p["fill"] = _rgba(fill)
    stroke = _fill(n, "strokes", report)
    if stroke is not None:
        p.update(stroke=True, strokeColor=_rgba(stroke), strokeWidth=float(n.get("strokeWeight", 1)))
        if out["type"] == "path":
            p.update(cap={"NONE": "butt", "ROUND": "round", "SQUARE": "square"}.get(n.get("strokeCap", "NONE"), "butt"),
                     join=n.get("strokeJoin", "MITER").lower())
    return out


def _text(n: dict, name: str, box: list, fill, report: list) -> dict:
    s = n.get("style", {})
    size = float(s.get("fontSize", 16))
    props = {"body": n.get("characters", ""), "size": size, "weight": float(s.get("fontWeight", 400)),
             "font": s.get("fontFamily", ""), "align": s.get("textAlignHorizontal", "LEFT").lower(),
             "tracking": s.get("letterSpacing", 0) / size, "color": _rgba(fill) if fill else "#000000"}
    if s.get("lineHeightPx"):
        props["lineHeight"] = s["lineHeightPx"] / size
    if props["align"] == "justified":
        report.append(f"text '{name}': justified text drawn left-aligned")
        props["align"] = "left"
    if not props["font"]:
        del props["font"]
    return {"type": "text", "name": name, "box": box, "props": props}


def _common(out: dict, n: dict, report: list) -> dict:
    p = out["props"]
    p["opacity"] = p.get("opacity", 1.0) * float(n.get("opacity", 1.0))
    if n.get("visible", True) is False:
        report.append(f"'{n['name']}' is hidden in Figma; imported with opacity 0")
        p["opacity"] = 0.0
    mode = n.get("blendMode", "NORMAL")
    if mode not in BLEND:
        report.append(f"'{n['name']}': blend mode {mode.lower().replace('_', ' ')} is not in the app; drawn normal")
    p["blend"] = BLEND.get(mode, "normal")
    return out
