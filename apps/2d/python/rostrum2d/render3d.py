"""3D render layers (`render3d`): a Rostrum3D item's finished render placed in a 2D composition, read-only.

docs/PLAN.md › Design asks for "3D layers live-linked from Rostrum3D: product renders sit in a 2D piece and update
when the 3D changes". AGENTS.md rule 8 keeps it a placed picture: 2D never combines the 3D app's layers or passes, it
shows the item's finished hand-off (its `rgba` EXR, shared/HANDOFFS.md § 2) as one picture, like a video layer. Mixing
passes and frames from several apps stays the Editor's job.

- The render is `rostrum_core.project.latest_render(folder, item, "pictures")` (or the version the layer pins).
- Needs the `render3d` extra (OpenEXR, OpenColorIO 2.5 = the 3D core's, numpy, Pillow), loaded on first use.
- Its EXR frames (scene-linear, premultiplied alpha) are turned once into straight-alpha sRGB PNGs through
  OpenColorIO with the 3D app's own rule (the config named by $OCIO, else the built-in CG config; the sRGB display's
  default view: core/src/image_out.cpp), so the picture matches the 3D app's PNG, with its alpha kept. Each frame is
  made at the layer's w × h and fit, in a content-keyed cache. The engine draws them as a `video` layer.
- A new 3D render is picked up by the next scene description (the screen's watch asks for one: render3d_watch.py).
- Out of date is told by content: the render's manifest `source.doc_hash` against the 3D document's hash now (older
  renders without one: by history step).
- Loud: no project folder, no such item, not a 3D item, not rendered yet, a pinned version that isn't there, a
  render with no EXR frames, a marker that isn't in the project. Out of date (the 3D document changed after the
  render) is not an error: `status` says so, and inspect_diagnose / the Problems list show it.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from pathlib import Path

from rostrum_core import RostrumError, codes, project, storage

CACHE_DIR = Path.home() / ".rostrum" / "cache" / "2d-render3d"
CACHE_BYTES = 4 << 30
CONVERTER = "1"              # bump when the conversion changes (it is in every cache key)
_FRAME_NO = re.compile(r"\.(\d+)\.exr$", re.I)


class NotRendered(RostrumError):
    """The layer's 3D item has no render (or not the pinned one) yet: scene.py may leave the layer out of frames
    where it isn't on screen, so the rest of a film can be looked at while its 3D shot renders."""


def _where(item: dict) -> str:
    return f'{item.get("id", "?")}.item'


def find(item: dict, folder) -> dict:
    """The render the layer shows: {item, name, version, path, exrs (sorted by frame), fps, made_at, source_seq}."""
    ref = item.get("item", "")
    if not ref:
        raise RostrumError(codes.BAD_ARGUMENT, _where(item), "a 3D render layer", "names no 3D item",
                           hint="Set its 3D item to the id of a Rostrum3D item of this project.")
    if not folder:
        raise RostrumError(codes.NOT_FOUND, _where(item), f'3D item "{ref}"', "can't be found: this document is not in a project folder")
    it = project.item(folder, ref)              # loud, listing the project's items, when there is none
    if it["kind"] != "3d":
        raise RostrumError(codes.BAD_ARGUMENT, _where(item), f'item "{ref}"', f'is a {it["kind"]} item, not a 3D one')
    pin = int(item.get("version", 0) or 0)
    pictures = [r for r in it["renders"] if r["kind"] == "pictures"]
    r = next((r for r in pictures if not pin or r["version"] == pin), None)
    if r is None:
        have = ", ".join(f'v{p["version"]:03d}' for p in pictures) or "none"
        what = f"has no render v{pin:03d}" if pin else "is not rendered yet"
        raise NotRendered(codes.NOT_FOUND, _where(item), f'{it["name"]} ({ref})', f"{what} (renders: {have})",
                           hint="Render it in Rostrum3D (render_still or render_video with EXR frames), or set Version to 0 for the newest.")
    exrs = sorted((f for f in r["files"] if f.lower().endswith(".exr")),
                  key=lambda f: int(m.group(1)) if (m := _FRAME_NO.search(f)) else 0)
    if not exrs:
        raise RostrumError(codes.NOT_FOUND, _where(item), f'{it["name"]} v{r["version"]:03d}', "has no EXR frames (the hand-off with transparency)",
                           hint="Render it again with EXR: render_still formats [png, exr], or render_video exr: true.")
    num, _, den = str(r["manifest"].get("frames", {}).get("fps", "24/1")).partition("/")
    return {"item": ref, "name": it["name"], "version": r["version"], "path": r["path"], "exrs": exrs,
            "fps": float(num) / float(den or 1), "made_at": r["manifest"].get("made_at", ""),
            "source_seq": r["manifest"].get("source", {}).get("history_entry"),
            "source_hash": r["manifest"].get("source", {}).get("doc_hash")}


def document_seq(folder, ref: str) -> int | None:
    """The 3D document's last saved step (its history file), or None when it can't be told."""
    try:
        lines = (Path(folder) / ".rostrum" / f"{ref}.history.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    return max((e["seq"] for e in map(json.loads, lines[1:]) if "seq" in e), default=0)


def document_hash(folder, ref: str) -> str | None:
    """The 3D document's content hash (as in a render's manifest `source.doc_hash`), or None when it can't be read."""
    try:
        text = storage.paths(folder, ref, ".trd")["doc"].read_text(encoding="utf-8")
        return storage.doc_hash(json.loads(text)["doc"])
    except (OSError, ValueError, KeyError):
        return None


def is_stale(r: dict, folder) -> bool:
    """Whether the 3D scene changed after this render. By content when the render recorded its hash (a re-run that
    changed nothing, or changed and changed back, is not out of date); older renders by history step."""
    if r["source_hash"] and (now := document_hash(folder, r["item"])):
        return now != r["source_hash"]
    now_seq = document_seq(folder, r["item"])
    return r["source_seq"] is not None and now_seq is not None and now_seq > r["source_seq"]


def status(item: dict, folder) -> dict:
    """What the layer shows and whether it is current: {ok, version, newest, stale, message}. Never raises."""
    try:
        r = find(item, folder)
        newest = find({**item, "version": 0}, folder)["version"]
    except RostrumError as e:
        return {"ok": False, "stale": False, "message": str(e)}
    stale = is_stale(r, folder)
    words = f'{r["name"]} v{r["version"]:03d}' + (f" (pinned; newest is v{newest:03d})" if newest != r["version"] else "")
    if stale:
        words += ": out of date: the 3D scene changed after this render"
    return {"ok": True, "version": r["version"], "newest": newest, "stale": stale, "message": words}


# --- the picture ---------------------------------------------------------------------------------------------------

_PROC = {}


def _processor():
    """scene_linear → the sRGB display's default view, as the 3D app makes its PNGs. (look name, CPU processor)"""
    import PyOpenColorIO as ocio
    name = os.environ.get("OCIO") or "ocio://cg-config-latest"
    if name not in _PROC:
        cfg = ocio.Config.CreateFromFile(name)
        display = next((d for d in cfg.getDisplays() if d.startswith("sRGB")), cfg.getDefaultDisplay())
        view = cfg.getDefaultView(display)
        t = ocio.DisplayViewTransform(src="scene_linear", display=display, view=view)
        _PROC[name] = (f"{name}|{display}|{view}", cfg.getProcessor(t).getDefaultCPUProcessor())
    return _PROC[name]


def _read_exr(path: Path):
    """The first (rgba) part as float32 h × w × 4: premultiplied, scene-linear."""
    import numpy as np
    import OpenEXR
    with OpenEXR.File(str(path)) as f:
        ch = f.parts[0].channels
        if "RGBA" in ch:
            return np.ascontiguousarray(ch["RGBA"].pixels, dtype=np.float32)
        rgb = [np.asarray(ch[c].pixels, dtype=np.float32) for c in "RGB"]
        a = np.asarray(ch["A"].pixels, dtype=np.float32) if "A" in ch else np.ones_like(rgb[0])
        return np.ascontiguousarray(np.stack(rgb + [a], -1))


def _fit(img, w: int, h: int, fit: str):
    """Resized in premultiplied form (no dark fringes at soft edges)."""
    from PIL import Image
    img = img.convert("RGBa")
    sw, sh = img.size
    if fit == "stretch":
        return img.resize((w, h), Image.LANCZOS).convert("RGBA")
    s = (max if fit == "cover" else min)(w / sw, h / sh)
    rw, rh = max(1, round(sw * s)), max(1, round(sh * s))
    out = Image.new("RGBa", (w, h), (0, 0, 0, 0))
    out.paste(img.resize((rw, rh), Image.LANCZOS), ((w - rw) // 2, (h - rh) // 2))
    return out.convert("RGBA")


def picture(exr: Path, w: int, h: int, fit: str) -> Path:
    """One EXR frame as a straight-alpha sRGB PNG at w × h, made once (named by its content and settings)."""
    import numpy as np
    from PIL import Image
    look, cpu = _processor()
    digest = hashlib.sha256(exr.read_bytes()).hexdigest()[:24]
    out = CACHE_DIR / (hashlib.sha256(f"{digest}|{w}x{h}|{fit}|{look}|{CONVERTER}".encode()).hexdigest()[:32] + ".png")
    if out.is_file():
        return out
    px = _read_exr(exr)
    a = np.clip(px[..., 3:4], 0.0, 1.0)
    rgba = px.copy()
    rgba[..., :3] = np.where(a > 1e-6, px[..., :3] / np.maximum(a, 1e-6), 0.0)    # straight colour for the view
    rgba[..., 3] = 1.0
    cpu.applyRGBA(rgba)
    rgba[..., 3:4] = a
    img = Image.fromarray((np.clip(rgba, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + ".partial.png")
    _fit(img, w, h, fit).save(tmp, format="PNG", compress_level=1)
    tmp.replace(out)
    _trim()
    return out


def node(node: dict, item: dict, fps: float, folder) -> dict:
    """The scene node: the engine's `video` layer over the render's frames, resampled to the comp's fps."""
    r = find(item, folder)
    props = dict(node["props"])
    w, h, fit = int(props["w"]), int(props["h"]), props.get("fit", "cover")
    if w < 2 or h < 2:
        raise RostrumError(codes.BAD_ARGUMENT, f'{item["id"]}.w', f"{w}×{h}", "must be at least 2 px each way")
    for k in ("item", "version"):
        props.pop(k, None)
    pngs = [picture(Path(r["path"]) / f, w, h, fit) for f in r["exrs"]]
    count = max(1, math.floor(len(pngs) * fps / r["fps"] + 1e-6))
    frames = [{"at": i, "src": str(pngs[min(len(pngs) - 1, math.floor(i * r["fps"] / fps + 1e-6))])} for i in range(count)]
    return {**node, "type": "video", "props": {**props, "src": str(pngs[0])}, "frames": frames}


def _trim():
    total = 0
    for f in sorted(CACHE_DIR.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True):
        total += f.stat().st_size
        if total > CACHE_BYTES:
            f.unlink(missing_ok=True)
