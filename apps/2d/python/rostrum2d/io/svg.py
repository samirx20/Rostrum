"""SVG → import tree. The engine reads the file with usvg (`rostrum2d-render svg-tree`, svg_tree.rs): CSS, `use`,
units and shapes resolved, every path absolute in the SVG's px. This module only maps that to the tree (tree.py).
Text comes in as text layers (editable; placed by its glyphs' box) or, with `text="outline"`, as paths that look
exactly like the source. Groups that only carried a transform are dissolved (their children keep their place).
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from ..engine import EngineError, find_exe

BLENDS = {"normal": "normal", "multiply": "multiply", "screen": "screen", "overlay": "overlay", "softlight": "soft-light"}


def svg_tree(path, text: str = "text") -> dict:
    """Read an SVG → the import tree. `text`: "text" (editable text layers) or "outline" (paths)."""
    if text not in ("text", "outline"):
        raise ValueError(f'text is "text" or "outline", not {text!r}')
    path = Path(path)
    with tempfile.TemporaryDirectory(prefix="rostrum-svg-") as tmp:
        run = subprocess.run([str(find_exe()), "svg-tree", str(path), tmp], capture_output=True, timeout=120)
        if run.returncode != 0:
            raise EngineError(f"svg-tree could not read {path}: {run.stderr.decode('utf-8', 'replace').strip()}")
        src = json.loads(run.stdout)
        report: list[str] = []
        layers = _nodes(src["layers"], report, text)
    if not layers:
        raise ValueError(f"{path.name} has nothing to import")
    return {"name": path.name, "width": src["width"], "height": src["height"], "layers": layers, "report": report}


def _nodes(nodes: list, report: list, text: str) -> list[dict]:
    out = []
    for n in nodes:
        name = n.get("id") or ""
        for note in n.get("notes", []):
            report.append(f"'{name or n['type']}': {note}")
        if n["type"] == "group":
            kids = _nodes(n["layers"], report, text)
            plain = n["opacity"] == 1 and n["blend"] == "normal" and not n["id"]
            if plain or len(kids) == 0:
                out += kids                               # a transform-only group: its children are already placed
                continue
            props = {"opacity": n["opacity"], "blend": _blend(n["blend"], name, report)}
            out.append({"type": "group", "name": name or "Group", "props": props, "layers": kids})
        elif n["type"] == "path":
            out += _path(n, name)
        elif n["type"] == "text":
            out.append(_text(n, name, report, text))
        elif n["type"] == "image" and n["file"]:
            img = Image.open(n["file"]).convert("RGBA")
            img.load()
            out.append({"type": "image", "name": name or "Image", "image": img, "props": {"fit": "stretch"},
                        "box": _box(n["bbox"])})
    return out


def _box(b) -> list[float]:
    return [b[0], b[1], max(b[2], 1.0), max(b[3], 1.0)]


def _alpha(colour: str, opacity: float) -> str:
    return colour if opacity >= 1 else colour + f"{round(opacity * 255):02x}"


def _path(n: dict, name: str) -> list[dict]:
    if not n["d"]:
        return []
    f, s = n["fill"], n["stroke"]
    props = {"d": n["d"], "filled": f is not None}
    if f:
        props.update(fill=_alpha(f["color"], f["opacity"]), fillRule=f["rule"])
    if s:
        props.update(stroke=True, strokeColor=_alpha(s["color"], s["opacity"]), strokeWidth=s["width"], cap=s["cap"],
                     join=s["join"], miter=max(s["miter"], 1.0))
        if s["dash"]:
            props.update(dash=s["dash"][0], gap=s["dash"][1] if len(s["dash"]) > 1 else s["dash"][0])
    return [{"type": "path", "name": name or "Path", "box": _box(n["bbox"]), "props": props}]


def _text(n: dict, name: str, report: list, mode: str) -> dict:
    label = name or n["text"].strip()[:30] or "Text"
    if mode == "outline" or not n["size"]:
        props = {"d": n["outline"], "fill": _alpha(n["color"] or "#000000", n["opacity"] or 1.0)}
        return {"type": "path", "name": label, "box": _box(n["bbox"]), "props": props}
    if "\n" in n["text"]:
        report.append(f"text '{label}': several lines; spacing between them is the app's, not the SVG's")
    props = {"body": n["text"], "size": n["size"], "weight": float(n["weight"] or 400), "align": "left",
             "color": _alpha(n["color"] or "#000000", n["opacity"] or 1.0)}
    if n["font"]:
        props["font"] = n["font"]
    return {"type": "text", "name": label, "box": _box(n["bbox"]), "props": props}


def _blend(mode: str, name: str, report: list) -> str:
    if mode not in BLENDS:
        report.append(f"group '{name}': blend mode {mode} drawn as normal")
    return BLENDS.get(mode, "normal")
