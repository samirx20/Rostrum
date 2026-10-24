"""One door for every import: a file (or a Figma frame) → the calls that put it into a composition, as ONE change, and the
report of what didn't come across. The Import panel and the MCP tool `run_import` both call `run`.

    kind (by the extension when not given): svg | pdf | psd | figma | image | video
    pdf: `page` counts from 1; page 0 = every page, one new composition each
    svg / pdf / psd / figma → the importer's tree → tree.prepare (names, places, checks every field) → doc.apply
    image / video           → one layer of that type, centred in the composition, shrunk to fit if bigger
    `plan` is the slow part (no change to the document, safe off the GUI thread), `apply` the one change; `run` = both.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image

from rostrum_core import project

from .. import settings
from . import tree as T
from .figma import figma_tree
from .svg import svg_tree

IMAGES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
VIDEOS = {".mp4", ".mov", ".webm", ".mkv", ".m4v", ".avi"}
KINDS = ("svg", "pdf", "psd", "figma", "image", "video")
FILTERS = "Images, video, SVG, PDF, PSD (*.svg *.pdf *.psd " + " ".join("*" + e for e in sorted(IMAGES | VIDEOS)) + ")"


def app_fonts() -> set[str] | None:
    """The family names the engine can draw (fontlist.py: the app's fonts and the computer's), so an imported text in
    another font is reported and set in the default one rather than refused. None when no engine is built (then nothing
    is checked)."""
    from ..engine import EngineError
    from ..fontlist import names
    try:
        return names()
    except EngineError:
        return None


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
    exe = settings.ffmpeg("ffprobe")              # fails loudly when there is none
    out = subprocess.run([exe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json",
                          str(path)], capture_output=True, timeout=60, creationflags=settings.NO_WINDOW)
    streams = json.loads(out.stdout or b"{}").get("streams") or []
    if out.returncode != 0 or not streams:
        raise ValueError(f"{path.name} is not a video ffprobe can read")
    return streams[0]["width"], streams[0]["height"]


def media_calls(doc_data: dict, comp: dict, into: str, kind: str, path: Path, at=None, folder=None) -> list[dict]:
    """layer.add + image.set / video.set: the file's own size (shrunk to fit the frame), centred (or centred on `at`, (x, y)).
    `folder` (the project): the file is copied into it first and the layer names it by its place there."""
    from rostrum_core import ids
    from rostrum_core.tree import index
    from ..kind import KIND
    w, h = _size_of(kind, path)
    k = min(1.0, comp["width"] / w, comp["height"] / h)
    src = str(path)
    if folder is not None:                       # the file is kept in the project (media/<kind>/), stored relative: the project can move
        src = project.add_file(folder, kind, path.stem, path)["file"]
    lid = ids.counted(index(doc_data, KIND.lists), kind)
    return [{"op": "layer.add", "target": [into], "args": {"type": kind, "id": lid, "name": path.stem}},
            {"op": f"{kind}.set", "target": [lid], "args": {"src": src, "w": round(w * k), "h": round(h * k),
                                                           "x": at[0] if at else comp["width"] / 2,
                                                           "y": at[1] if at else comp["height"] / 2}}]


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
        from .pdf import pdf_tree                  # pypdf / pdfium load when a PDF is read (io/__init__.py)
        return pdf_tree(path, max(page, 1) - 1)
    if kind == "psd":
        from .psd import psd_tree                  # psd_tools loads when a PSD is read
        return psd_tree(path)
    raise ValueError(f"unknown kind {kind!r}: {', '.join(KINDS)}")


class Cancelled(Exception):
    """The caller's `cancelled()` said stop: nothing was applied."""


def _stage(progress, cancelled, fraction: float, words: str):
    """Between stages: stop if asked, else say how far along."""
    if cancelled and cancelled():
        raise Cancelled("Cancelled: nothing imported.")
    if progress:
        progress(fraction, words)


def _pages(doc, comp, path, progress=None, cancelled=None) -> dict:
    """pdf page 0: every page into its own new composition (named "Page N" or the page's label, the page's size, the open
    composition's frame rate and length), all in one change. → the plan, with the new comps' ids in "comps"."""
    from rostrum_core.tree import index
    from ..kind import KIND
    _stage(progress, cancelled, 0.1, "Reading the PDF")
    from .pdf import pdf_pages
    trees, taken = pdf_pages(path), set(index(doc.data, KIND.lists))
    calls, report, comps = [], [], []
    for i, tr in enumerate(trees):
        _stage(progress, cancelled, 0.2 + 0.7 * i / len(trees), f"Page {i + 1} of {len(trees)}")
        cid = T._id(tr["comp"], "comp", taken)
        calls.append({"op": "comp.add", "args": {"id": cid, "name": tr["comp"], "width": round(tr["width"]), "height": round(tr["height"]),
                                                 **{k: comp[k] for k in ("fps", "duration") if k in comp}}})
        page_calls, page_report = T.prepare(doc, tr, cid, app_fonts(), taken)
        calls, report, comps = calls + page_calls, report + page_report, comps + [cid]
    return {"name": trees[0]["name"], "kind": "pdf", "calls": calls, "report": report, "comps": comps, "into": None,
            "label": f"Import {trees[0]['name']} ({len(trees)} pages)"}


def plan(doc, comp_id: str, path=None, kind: str | None = None, page: int = 1, text: str = "text", figma: dict | None = None,
         into: str | None = None, fit: bool = False, progress=None, cancelled=None, at=None) -> dict:
    """The slow part of an import, with no change to the document (so it may run off the GUI thread): read, download, parse,
    place. → {"name", "kind", "calls": [ops], "report", "label", "into", "comps"?}; `apply` makes the one change.
    `fit` (svg / pdf / psd / figma): the picture's visible content box is centred in the composition at its own size, scaled
    down to fit inside it (with a margin) only when it is bigger; a whole-PDF import (page 0) makes comps of the page's size.
    `at` (x, y): where a picture or clip lands (dropped on the canvas); a page is always fitted.
    `progress(fraction, words)` and `cancelled()` are called between stages; a True from `cancelled` raises Cancelled."""
    kind = kind or ("figma" if figma else kind_of(path))
    if kind == "pdf" and page == 0:                          # page 0 = every page, a composition each (the open comp only sets fps and length)
        if into and into != comp_id:
            raise ValueError("a whole-PDF import makes its own compositions; `into` is for one page")
        if not Path(path or "").is_file():
            raise ValueError(f"no file at {path}")
        return _pages(doc, doc.item(comp_id), Path(path), progress, cancelled)
    into = into or comp_id
    if not doc.has(into) or doc.item(into)["type"] not in ("comp", "group"):
        raise ValueError(f"'{into}' is not a composition or a group to import into")
    comp = doc.item(comp_id)
    if kind in ("image", "video"):
        path = Path(path or "")
        if not path.is_file():
            raise ValueError(f"no file at {path}")
        _stage(progress, cancelled, 0.3, f"Reading {path.name}")
        calls, report, name = media_calls(doc.data, comp, into, kind, path, at, Path(doc.folder) if doc.folder else None), [], path.name
    else:
        _stage(progress, cancelled, 0.1, "Downloading the frame" if kind == "figma" else f"Reading the {kind.upper()}")
        tr = tree_of(kind, path, page, text, figma)
        _stage(progress, cancelled, 0.6, "Placing the layers")
        calls, report = T.prepare(doc, tr, into, app_fonts(), fit=(comp["width"], comp["height"]) if fit else None)
        name = tr["name"]
    _stage(progress, cancelled, 0.95, "Ready to put in")
    return {"name": name, "kind": kind, "calls": calls, "report": report, "into": into, "label": f"Import {name}"}


def apply(doc, who, p: dict) -> dict:
    """The one change (one undo step) of a plan. Call it on the thread that owns the document.
    → {"name", "kind", "calls": n, "layers": [new top-level ids in `into`], "report"}; a whole PDF also has "comps"."""
    into = p["into"]
    before = {c["id"] for c in doc.item(into).get("layers", [])} if into else set()
    doc.apply(p["calls"], who, label=p["label"])
    out = {"name": p["name"], "kind": p["kind"], "calls": len(p["calls"]), "report": p["report"]}
    if p.get("comps"):
        return {**out, "layers": [], "comps": p["comps"]}
    return {**out, "layers": [c["id"] for c in doc.item(into).get("layers", []) if c["id"] not in before]}


def run(doc, who, comp_id: str, path=None, kind: str | None = None, page: int = 1, text: str = "text",
        figma: dict | None = None, into: str | None = None, fit: bool = False) -> dict:
    """Import into `into` (a group of the composition; default the composition). One change, all or nothing: plan + apply.
    → {"name", "kind", "calls": n, "layers": [new top-level ids in `into`], "report": [what didn't come across]}."""
    return apply(doc, who, plan(doc, comp_id, path, kind, page, text, figma, into, fit))
