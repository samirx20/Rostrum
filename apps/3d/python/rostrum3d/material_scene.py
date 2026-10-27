"""The document's materials → the scene's `materials` (ENGINE_CONTRACT.md § 2, Materials), for compile.describe.

Every field is sent (defaults filled in, colours linear; the stylized blocks' Lines, Light to colour and Halftone too,
the core writing them into each material's Stylized and Cycles shaders) except `emissionRender`, which is resolved here: a 2D item's
newest finished "pictures" render (rostrum_core.project.latest_render) playing on the surface. It becomes
`emissionTexture`: one PNG for a still render, else (in the material's `anim`) one PNG per frame of the shot, the
2D frame at the same moment: shot frame f is at f / fps seconds, and the 2D file numbered n shows 2D time
(n − first) / fps2 + start (the manifest's frames.first and frames.start), so f shows file
first + floor((f / fps − start) × fps2), held at the first and last file. The read-only reverse of 2D's render3d
layer (P17). Loud: no project folder, no such item, not a 2D item, no render, a render that isn't PNG pictures, a
frame file that is missing.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

from rostrum_core import RostrumError, codes, project

from .material_fields import DOC_ONLY, MATERIAL

_FRAME = re.compile(r"\.(\d+)\.png$", re.I)


def _render(where: str, ref: str, folder) -> tuple[dict, dict[int, Path]]:
    """The newest pictures render of 2D item `ref` and its PNG frames by file number."""
    if not folder:
        raise RostrumError(codes.NOT_FOUND, where, f'2D item "{ref}"', "can't be found: this document is not in a project folder")
    it = project.item(folder, ref)                  # loud, listing the project's items, when there is none
    if it["kind"] != "2d":
        raise RostrumError(codes.BAD_ARGUMENT, where, f'item "{ref}"', f'is a {it["kind"]} item, not a 2D one')
    r = project.latest_render(folder, ref, "pictures")
    if r is None:
        raise RostrumError(codes.NOT_FOUND, where, f'{it["name"]} ({ref})', "is not rendered yet",
                           hint="Render it in Rostrum2D as a PNG sequence (render_export format png).")
    pngs = {int(m.group(1)): Path(r["path"]) / f for f in r["files"] if (m := _FRAME.search(f))}
    if not pngs:
        raise RostrumError(codes.BAD_ARGUMENT, where, f'{it["name"]} v{r["version"]:03d}',
                           f'has no PNG frames (its files: {", ".join(r["files"][:4]) or "none"})',
                           hint="Render it in Rostrum2D as a PNG sequence (render_export format png); an mp4 can't be put on a surface.")
    return r, pngs


def _fps(manifest: dict) -> float:
    num, _, den = str(manifest.get("frames", {}).get("fps", "24/1")).partition("/")
    return float(num) / float(den or 1)


def frames_for(where: str, ref: str, folder, shot_frames: range, fps: float) -> list[str]:
    """The PNG each shot frame shows (absolute paths, one per frame of `shot_frames`)."""
    r, pngs = _render(where, ref, folder)
    frames = r["manifest"].get("frames", {})
    first, last = int(frames.get("first", min(pngs))), int(frames.get("last", max(pngs)))
    start, fps2 = float(frames.get("start", 0.0)), _fps(r["manifest"])
    out = []
    for f in shot_frames:
        n = min(last, max(first, first + math.floor((f / fps - start) * fps2 + 1e-6)))
        if n not in pngs:
            raise RostrumError(codes.NOT_FOUND, where, f'frame {n} of {ref} v{r["version"]:03d}',
                               f"is missing from {r['path']} (its manifest says frames {first}–{last})",
                               hint="Render the 2D item again.")
        out.append(str(pngs[n]))
    return out


def prop_out(name: str, value):
    """One material field's value as the scene sends it (a colour linear, as compile.describe does): the live
    `material` request's props (ENGINE_CONTRACT.md § 4) are the same as the scene's."""
    from .compile import _out
    return _out(next(p for p in MATERIAL if p.name == name), value)


def materials(data: dict, shot_frames: range, fps: float, folder, out_value) -> list[dict]:
    """The scene's material list for one shot. `out_value(param, value)`: the compiler's one way a value is sent."""
    out = []
    for m in data.get("materials", []):
        props = {p.name: out_value(p, m.get(p.name, p.default)) for p in MATERIAL if p.name not in DOC_ONLY}
        node = {"id": m["id"], "props": props}
        ref = m.get("emissionRender", "")
        if ref and m.get("emissionStrength", 0) and not m.get("emissionTexture", ""):
            files = frames_for(f'{m["id"]}.emissionRender', ref, folder, shot_frames, fps)
            props["emissionTexture"] = files[0]
            if len(set(files)) > 1:
                node["anim"] = {"emissionTexture": files}
        out.append(node)
    return out
