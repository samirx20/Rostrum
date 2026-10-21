"""One door for every import: a file (or a Figma frame) → the calls that put it into a composition, as ONE change, and the
report of what didn't come across. The Import panel and the MCP tool `run_import` both call `run`.

    kind (by the extension when not given): svg | pdf | psd | figma | image | video
    svg / pdf / psd / figma → the importer's tree → tree.prepare (names, places, checks every field) → doc.apply
    image / video           → one layer of that type, centred in the composition, shrunk to fit if bigger
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageFont

from .. import engine
from . import tree as T
from .figma import figma_tree
from .pdf import pdf_tree
from .psd import psd_tree
from .svg import svg_tree

IMAGES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
VIDEOS = {".mp4", ".mov", ".webm", ".mkv", ".m4v", ".avi"}
KINDS = ("svg", "pdf", "psd", "figma", "image", "video")
FILTERS = "Images, video, SVG, PDF, PSD (*.svg *.pdf *.psd " + " ".join("*" + e for e in sorted(IMAGES | VIDEOS)) + ")"


def app_fonts() -> set[str] | None:
    """The family names the engine can draw (its fonts folder), so an imported text in another font is reported and set in the
    default one rather than refused by the engine later. None when the folder can't be found (then nothing is checked)."""
    folder = Path(os.environ.get("ROSTRUM2D_FONTS") or engine.HERE / "engine" / "fonts")
    names: set[str] = set()
    for f in folder.glob("*.[to]tf"):
        family = ImageFont.truetype(str(f), 12).getname()[0]
        names |= {family, family.removesuffix(" Variable")}
    return names or None


def kind_of(path) -> str:
    ext = Path(path).suffix.lower()
    for kind, exts in (("svg", {".svg"}), ("pdf", {".pdf"}), ("psd", {".psd"}), ("image", IMAGES), ("video", VIDEOS)):
        if ext in exts:
            return kind
    raise ValueError(f"can't import a '{ext or Path(path).name}' file: it is {', '.join(KINDS[:4])}, an image or a video")


def _size_of(kind: str, path: Path) -> tuple[int, int]:
    if kind == "image":
        with Image.open(path) as im:
            return im.size
    exe = shutil.which("ffprobe")
    if exe is None:
        raise RuntimeError("ffprobe is needed to read a video's size and was not found")
    out = subprocess.run([exe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json",
                          str(path)], capture_output=True, timeout=60)
    streams = json.loads(out.stdout or b"{}").get("streams") or []
    if out.returncode != 0 or not streams:
        raise ValueError(f"{path.name} is not a video ffprobe can read")
    return streams[0]["width"], streams[0]["height"]


def media_calls(doc_data: dict, comp: dict, into: str, kind: str, path: Path) -> list[dict]:
    """layer.add + image.set / video.set: the file's own size (shrunk to fit the frame), centred."""
    from rostrum_core import ids
    from rostrum_core.tree import index
    from ..kind import KIND
    w, h = _size_of(kind, path)
    k = min(1.0, comp["width"] / w, comp["height"] / h)
    lid = ids.counted(index(doc_data, KIND.lists), kind)
    return [{"op": "layer.add", "target": [into], "args": {"type": kind, "id": lid, "name": path.stem}},
            {"op": f"{kind}.set", "target": [lid], "args": {"src": str(path), "w": round(w * k), "h": round(h * k),
                                                           "x": comp["width"] / 2, "y": comp["height"] / 2}}]


def tree_of(kind: str, path=None, page: int = 1, text: str = "text", figma: dict | None = None) -> dict:
    """The importer's tree for a document kind. `page` counts from 1 (pdf)."""
    if kind == "figma":
        if not figma or not figma.get("key"):
            raise ValueError("a Figma import needs the file key (and a token)")
        return figma_tree(figma["key"], figma.get("frame") or None, figma.get("token") or None)
    path = Path(path or "")
    if not path.is_file():
        raise ValueError(f"no file at {path}")
    if kind == "svg":
        return svg_tree(path, text)
    if kind == "pdf":
        return pdf_tree(path, max(page, 1) - 1)
    if kind == "psd":
        return psd_tree(path)
    raise ValueError(f"unknown kind {kind!r}: {', '.join(KINDS)}")


def run(doc, who, comp_id: str, path=None, kind: str | None = None, page: int = 1, text: str = "text",
        figma: dict | None = None, into: str | None = None) -> dict:
    """Import into `into` (a group of the composition; default the composition). One change, all or nothing.
    → {"name", "kind", "calls": n, "layers": [new top-level ids in `into`], "report": [what didn't come across]}."""
    kind = kind or ("figma" if figma else kind_of(path))
    into = into or comp_id
    if not doc.has(into) or doc.item(into)["type"] not in ("comp", "group"):
        raise ValueError(f"'{into}' is not a composition or a group to import into")
    comp = doc.item(comp_id)
    if kind in ("image", "video"):
        path = Path(path or "")
        if not path.is_file():
            raise ValueError(f"no file at {path}")
        calls, report, name = media_calls(doc.data, comp, into, kind, path), [], path.name
    else:
        tr = tree_of(kind, path, page, text, figma)
        calls, report = T.prepare(doc, tr, into, app_fonts())
        name = tr["name"]
    holder = doc.item(into)
    before = {c["id"] for c in holder.get("layers", [])}
    doc.apply(calls, who, label=f"Import {name}")
    layers = [c["id"] for c in doc.item(into).get("layers", []) if c["id"] not in before]
    return {"name": name, "kind": kind, "calls": len(calls), "layers": layers, "report": report}
