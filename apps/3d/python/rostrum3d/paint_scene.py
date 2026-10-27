"""Painted meshes and clays → the scene (SPEC §5 "Materials meet paint"), for compile.describe. For each mesh or clay
holding paint layers and each channel they paint (paint_fields.CHANNELS), the channel's layers (the shared kit's
canvas, its own cache) are laid over the material's own value where painted: its colour or number, or its own picture
for that channel. The result is one content-keyed PNG per channel (the shared cache, kind "paint": `surface.png`, and
beside it `alpha.png`, where anything is painted, which coverage.py reads): made once, then only read. The item gets
a material of its own, `<item>__paint`, a copy of its material with those pictures set (baseColorTexture,
roughnessTexture, bumpTexture, metallicTexture, emissionTexture); both renderers read them on the mesh's `uvs` or the
clay's unfolded surface. An editable mesh's face materials get painted copies too (`<item>__paint__<material>`), so
the paint shows on every face. The pictures bleed a few texels past each piece's edge (paint_bleed.py): no seam line.

Some paint needs the engine first, and waits in `scene["paintLater"]` (a JSON recipe per item): a clay's strokes are
laid on its unfolded surface for this shape (clay_paint.laid), which the core writes when it loads the clay (node
`paint` {file, size}: clay_paint.surface_file); strokes from the view and projected pictures are laid from texel
pictures (paint_view.py), which the engine draws from the loaded scene (texels.py). `send(scene, load, texels)` loads
the scene without the waiting pictures, then makes them (`finish`) and loads again. A texel picture the shared cache
already holds (texels.cached) is used at once: no second load.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
from rostrum_core.cache import CACHE, cache_key
from rostrum_paint import canvas

from . import clay_paint, paint_bleed, paint_view
from .material_fields import DOC_ONLY, MATERIAL
from .paint_fields import CHANNELS

VERSION = f"rostrum3d-paint-surface@2+{canvas.ENGINE_VERSION}"
LATER = "paintLater"
COVERAGE = "paintCoverage"              # the screen's coverage tint (coverage.py): never sent to the engine


def canvases(items: list):
    """Every mesh or clay holding paint layers, children too."""
    for it in items:
        if it.get("type") in ("mesh", "clay") and it.get("paints"):
            yield it
        yield from canvases(it.get("children", []))


def _nodes(nodes: list, out: dict) -> dict:
    for n in nodes:
        out[n["id"]] = n
        _nodes(n.get("children", []), out)
    return out


def engine_scene(scene: dict) -> dict:
    """`scene` as it is sent: without the waiting paint recipes or the screen's tint option."""
    if LATER not in scene and COVERAGE not in scene:
        return scene
    return {k: v for k, v in scene.items() if k not in (LATER, COVERAGE)}


def geometry_scene(scene: dict) -> dict:
    """What texel pictures depend on (texels.cached's scene): the scene without its materials, which item wears
    which material, the clays' paint files and the waiting paint. The same before and after the paint is laid, so a
    picture drawn after the first load is found again by the next compile."""
    def strip(n):
        out = {k: v for k, v in n.items() if k not in ("paint", "children")}
        out["props"] = {k: v for k, v in n.get("props", {}).items() if k not in ("material", "faceMaterials")}
        if n.get("children"):
            out["children"] = [strip(c) for c in n["children"]]
        return out
    return {**{k: v for k, v in scene.items() if k not in (LATER, COVERAGE, "materials", "items")},
            "items": [strip(n) for n in scene.get("items", [])]}


def _rgb(hex_: str) -> list[float]:
    return [int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)]


def _under(channel: str, mat: dict) -> tuple:
    """What the paint sits over: ("file", path) for the material's own picture of the channel, else ("value", [r, g, b]
    sRGB 0..1, or [v] for a raw number)."""
    _, picture, own, raw = CHANNELS[channel]
    if channel == "glow" and mat.get("emissionRender"):
        return "value", [0.0, 0.0, 0.0]             # a playing 2D render can't be painted over yet: paint replaces it
    if mat.get(picture):
        return "file", mat[picture]
    if channel == "glow":
        return "value", _rgb(mat["emissionColor"]) if mat["emissionStrength"] else [0.0, 0.0, 0.0]
    if own is None:
        return "value", [0.5]                       # Relief: unpainted is middle grey, flat (black sinks, white raises)
    return "value", [float(mat[own])] if raw else _rgb(mat[own])


def _over(dst: np.ndarray, src: np.ndarray, opacity: float = 1.0) -> np.ndarray:
    """Straight-alpha `src` over straight-alpha `dst` (both h × w × 4, 0..1)."""
    a = src[..., 3:] * opacity
    out_a = a + dst[..., 3:] * (1 - a)
    rgb = (src[..., :3] * a + dst[..., :3] * dst[..., 3:] * (1 - a)) / np.maximum(out_a, 1e-6)
    return np.concatenate([np.where(out_a > 1e-6, rgb, 0), out_a], axis=-1)


def _paint_rgba(held: dict, size: int, splats: dict) -> np.ndarray:
    """The channel's layers as size × size × 4 straight RGBA uint8 (the kit's own bytes when nothing is projected). A
    projected layer is its picture with its own strokes over it, laid normally over what is below (the layers between
    projected ones: the kit's, as one)."""
    if not splats:
        return canvas.rgba8(held, size, size)
    out, run = np.zeros((size, size, 4), np.float32), []

    def flush():
        nonlocal out
        if run:
            out = _over(out, canvas.rgba8({**held, "paints": list(run)}, size, size).astype(np.float32) / 255)
            run.clear()
    for layer in held["paints"]:
        if layer["id"] not in splats:
            run.append(layer)
            continue
        flush()
        if layer.get("visible", True) and layer.get("opacity", 1) > 0:
            own = canvas.layer_rgba(held, layer["id"], size, size).astype(np.float32) / 255
            out = _over(out, _over(splats[layer["id"]], own), float(layer.get("opacity", 1)))
    flush()
    return (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)


def _picture(held: dict, channel: str, layers: list, size: int, under: tuple, surface: str = "", trim=None,
             splats=None, extra=None, pieces=None) -> Path:
    raw = CHANNELS[channel][3]
    held = {"id": held["id"], "paints": layers, "paintmasks": held.get("paintmasks", [])}
    splats = {k: v for k, v in (splats or {}).items() if any(layer["id"] == k for layer in layers)}
    extra = extra or {}
    projected = {k: v for k, v in extra.get("projected", {}).items() if k in splats}
    settings = {"size": size, "channel": channel, "under": list(under),
                **({"surface": surface, "trim": clay_paint.TRIM} if surface else {}),
                **({"bleed": extra["bleed"]} if extra.get("bleed") else {}),
                **({"projected": projected} if projected else {})}
    key = cache_key("paint.surface", VERSION, [canvas.content_key(held, size, size)], settings)
    if CACHE.get("paint", key):
        return CACHE.path("paint", key) / "surface.png"

    def make(tmp: Path):
        from PIL import Image
        px = _paint_rgba(held, size, splats)              # uint8 throughout: a 2048² picture in float cost ~0.1 s
        a = px[..., 3]
        if trim is not None:                              # a clay's: no spill into other pieces
            a = (np.clip(trim(a[..., None].astype(np.float32) / 255)[..., 0], 0, 1) * 255 + 0.5).astype(np.uint8)
        if raw:                                           # raw channels: the brush colour's grey
            paint = (px[..., 0].astype(np.uint16) + px[..., 1] + px[..., 2] + 1) // 3
            paint = paint[..., None]
        else:
            paint = px[..., :3]
        if under[0] == "file":
            with Image.open(under[1]) as im:
                base = np.asarray(im.convert("L" if raw else "RGB").resize((size, size)))
            base = base[..., None] if raw else base
        else:
            base = np.asarray(np.round(np.asarray(under[1], np.float32) * 255), np.uint16)
        a16 = a[..., None].astype(np.uint16)
        out = ((paint * a16 + base * (255 - a16) + 127) // 255).astype(np.uint8)
        if pieces is not None:
            paint_bleed.bleed(out, pieces, a > 0, size)
        img = out[..., 0] if raw else out
        Image.fromarray(img, "L" if raw else "RGB").save(tmp / "surface.png", compress_level=1)
        Image.fromarray(a, "L").save(tmp / "alpha.png", compress_level=1)
    return CACHE.put("paint", key, make, {"item": held["id"], "channel": channel, "size": size}) / "surface.png"


def _source(where: str, src: str, folder) -> str:
    """A projected picture's file: a path (from the project folder when not absolute), or "2d:<id>": that 2D item's
    newest pictures render, its first frame (material_scene._render: loud when there is none)."""
    if src.startswith("2d:"):
        from .material_scene import _render
        _, pngs = _render(where, src[3:], folder)
        return str(pngs[min(pngs)])
    f = Path(src)
    if not f.is_absolute() and folder:
        f = Path(folder) / f
    if not f.is_file():
        raise ValueError(f"{where}: the projected picture {src} is not there ({f})")
    return str(f)


def _job(item: dict, node: dict, sent: dict, own: dict, out_value, folder) -> dict:
    """One painted item's recipe (JSON): its paint, the materials under it, its projected pictures' files."""
    def mat_of(mid):
        base = sent.get(mid) or {"props": {p.name: out_value(p, p.default) for p in MATERIAL if p.name not in DOC_ONLY}}
        return {"mat": {p.name: own.get(mid, {}).get(p.name, p.default) for p in MATERIAL},
                "base": {k: base[k] for k in ("props", "anim") if base.get(k)}}
    keep = ("id", "type", "paints", "paintmasks", "paintSize", "uvs", "faceCounts")
    job = {"item": {k: item[k] for k in keep if k in item}, **mat_of(node["props"].get("material", ""))}
    faces = sorted({m for m in node["props"].get("faceMaterials") or [] if m})
    if faces:
        job["faces"] = {m: mat_of(m) for m in faces}
    sources = {layer["id"]: _source(f'{item["id"]}.{layer["id"]}.projectSource', p["source"], folder)
               for layer in item["paints"] if (p := paint_view.projected_of(layer)) is not None}
    if sources:
        job["sources"] = sources
    job["texels"] = paint_view.requests(item)
    return job


def paint(scene: dict, data: dict, out_value, folder=None, texels=None) -> None:
    """Give every painted mesh and clay of `scene` (compile.describe's, from document `data`) its painted material,
    in place; one still waiting for the engine (a clay's surface, a texel picture): its recipe in scene["paintLater"].
    `out_value(param, value)`: the compiler's one way a value is sent. `folder`: the project folder (projected
    pictures). `texels`: an engine's ask (req -> reply), to draw a missing texel picture now instead of waiting."""
    nodes = _nodes(scene["items"], {})
    sent = {m["id"]: m for m in scene["materials"]}
    own = {m["id"]: m for m in data.get("materials", [])}
    jobs = []
    for item in canvases(data.get("items", [])):
        node = nodes.get(item["id"])
        if node is None:
            continue
        job = _job(item, node, sent, own, out_value, folder)
        ready = True
        if item["type"] == "clay":
            if not node.get("steps"):
                continue                                 # an empty clay: no surface to paint on
            size = item.get("paintSize", 2048)
            f = clay_paint.surface_file(node["steps"][-1]["key"], node["props"]["detail"], size)
            node["paint"] = {"file": str(f), "size": size}
            ready = f.is_file()
        jobs.append((node, job, ready))
    for node, job, ready in jobs:                        # every node is final now: the texel pictures' key
        pics = _pictures(scene, job, texels) if ready else None
        if pics is None:
            scene.setdefault(LATER, []).append(job)
        else:
            _apply(scene, node, job, pics)


def _pictures(scene: dict, job: dict, texels_fn) -> dict | None:
    """The job's texel pictures by request (paint_view.texel_key), drawn through `texels_fn` when given, else only the
    ones the shared cache holds: None when one is missing."""
    if not job["texels"]:
        return {}
    from . import texels
    geo = geometry_scene(scene)
    out = {}
    for r in job["texels"]:
        pic = texels.cached(geo, r, texels_fn)
        if pic is None:
            return None
        out[paint_view.texel_key(r)] = pic
    return out


def _splats(job: dict, pics: dict, held: dict) -> tuple[dict, dict]:
    """({layer id: its projected picture laid on the canvas}, {layer id: what that depends on, for the cache key})."""
    from PIL import Image
    size = job["item"].get("paintSize", 2048)
    splats, keys = {}, {}
    for layer in held["paints"]:
        p = paint_view.projected_of(layer)
        if p is None:
            continue
        req = paint_view.project_req(p, size)
        f = Path(job["sources"][layer["id"]])
        st = f.stat()
        k = hashlib.sha1(json.dumps([job["item"]["id"], paint_view.texel_key(req), _pic_id(pics[paint_view.texel_key(req)]),
                                     str(f), st.st_mtime_ns, st.st_size, size]).encode()).hexdigest()
        with Image.open(f) as im:
            rgba = np.asarray(im.convert("RGBA"), np.float32) / 255
        splats[layer["id"]] = paint_view.splat(pics[paint_view.texel_key(req)], job["item"]["id"], rgba, size, k)
        keys[layer["id"]] = k
    return splats, keys


def _pic_id(pic) -> str:
    """What a texel picture is (its file when it has one, else a hash of its pixels)."""
    f = getattr(pic, "file", None)
    if f:
        return str(f)
    return hashlib.sha1(np.ascontiguousarray(pic.uv).tobytes() + np.ascontiguousarray(pic.item).tobytes()).hexdigest()


def _apply(scene: dict, node: dict, job: dict, pics: dict) -> None:
    """One painted item's pictures and its `<id>__paint` material(s) (job: `_job`'s recipe; pics: its texel pictures)."""
    item = job["item"]
    size = item.get("paintSize", 2048)
    surface = clay_paint.read(node["paint"]["file"]) if "paint" in node else None
    held = clay_paint.laid(item, surface) if surface is not None else item
    if pics:
        held = paint_view.laid(held, pics, size)
    splats, splat_keys = _splats(job, pics, held) if job.get("sources") else ({}, {})
    pieces = paint_bleed.pieces(item, surface, size)
    extra = {"projected": splat_keys, "bleed": paint_bleed.key(item, surface, size)}
    by_channel: dict[str, list] = {}
    for layer in held["paints"]:
        by_channel.setdefault(layer.get("channel", "colour"), []).append(layer)
    own_layers: dict[str, list] = {}
    for layer in item.get("paints", []):
        own_layers.setdefault(layer.get("channel", "colour"), []).append(layer)

    def material(mat: dict, base: dict, mid: str) -> None:
        props = dict(base["props"])
        for channel, layers in by_channel.items():
            trim = None
            if surface is not None:
                trim = lambda a, ls=own_layers.get(channel, []): clay_paint.trim(surface, ls, a)  # noqa: E731
            props[CHANNELS[channel][1]] = str(_picture(held, channel, layers, size, _under(channel, mat),
                                                       surface.key if surface is not None else "", trim, splats,
                                                       extra, pieces))
        if "glow" in by_channel and not props.get("emissionStrength"):
            props["emissionStrength"] = 1.0        # painted glow shows at strength 1 on a material that had none
        new = {"id": mid, "props": props}
        if base.get("anim") and "glow" not in by_channel:
            new["anim"] = base["anim"]
        scene["materials"].append(new)

    material(job["mat"], job["base"], f"{item['id']}__paint")
    node["props"]["material"] = f"{item['id']}__paint"
    faces = job.get("faces") or {}
    for m, held_mat in faces.items():
        material(held_mat["mat"], held_mat["base"], f"{item['id']}__paint__{m}")
    if faces:
        node["props"]["faceMaterials"] = [f"{item['id']}__paint__{m}" if m else m
                                          for m in node["props"]["faceMaterials"]]


def finish(scene: dict, later: list, texels=None) -> dict:
    """A copy of `scene` (loaded once without its waiting pictures, so the core has written the clays' surfaces and can
    draw texel pictures) with those pictures made and set. `texels(req) -> reply`: the engine's texels request (the
    engine program's or the window's). Fails loudly when a surface is still missing or a picture can't be drawn."""
    done = copy.deepcopy(scene)
    nodes = _nodes(done["items"], {})
    for job in later:
        node = nodes[job["item"]["id"]]
        if "paint" in node:
            f = Path(node["paint"]["file"])
            if not f.is_file():
                raise RuntimeError(f'clay {job["item"]["id"]}: the 3D engine loaded it but wrote no unfolded surface '
                                   f"at {f}, so its paint can't be laid (see the engine's log)")
        if job["texels"] and texels is None:
            raise RuntimeError(f'{job["item"]["id"]}: its paint from the view needs the engine\'s texel pictures, and '
                               "this caller gave paint_scene.finish no `texels` ask")
        _apply(done, node, job, _pictures(scene, job, texels))
    return done


def send(scene: dict, load, texels=None):
    """Load `scene` through `load(scene)` (an engine's). A scene with paint waiting for the engine (paintLater) is
    loaded without it first, then again with its pictures (`finish`, texel pictures through `texels(req)`): what the
    second load returns."""
    later = scene.get(LATER)
    if not later:
        return load(engine_scene(scene))
    first = engine_scene(scene)
    load(first)
    return load(finish(first, later, texels))


def surface_of(scene: dict, item_id: str) -> Path | None:
    """The clay `item_id`'s unfolded surface file in `scene` when it is made, else None."""
    node = _nodes(scene.get("items", []), {}).get(item_id) or {}
    f = Path(node["paint"]["file"]) if node.get("paint") else None
    return f if f is not None and f.is_file() else None


_canvases = canvases                     # the older name
