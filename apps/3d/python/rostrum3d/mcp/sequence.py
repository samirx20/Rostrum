"""A shot's frames as numbered pictures (png and/or exr), as one project render version: the one code path of the
render sheet's "the shot" (screen3d/export3d.py) and the Render page's queue (screen3d/queue.py). The frames are
drawn into `vNNN.partial/`, renumbered to the hand-off numbering (FIRST = 1001), counted, and only then finished with
a manifest; a failed render leaves just the `.partial` folder, which is never listed as a version; a stopped one (`stopped()`, a
cancel) leaves nothing.
"""
from __future__ import annotations

from pathlib import Path

from rostrum_core.errors import RostrumError, codes

from . import draw
from .render import FIRST, _finish, _folder, _manifest, _renumber, kept_unless_stopped


def sequence(where: str, doc, info: dict, scene: dict, engine, size: tuple[int, int], formats: list[str], cycles: dict,
             folder=None, stem: str | None = None, progress=None, passes: list[str] | None = None, stopped=None,
             renderer: str = "cycles") -> tuple[Path, list[Path]]:
    """Frames info["start"]..info["end"] of the shot through its camera with Cycles (or `renderer`; `cycles`: that
    renderer's request settings, render_fields.engine_fields). `progress(done, total)` is called
    as frames land (it may raise to stop). `passes`: the EXR's extra layers (render_fields.PASSES; only with an exr),
    listed in the manifest's `exr`. Blocking: call it from a job. Returns (the finished folder, its files)."""
    f0, f1, (w, h) = info["start"], info["end"], size
    name = stem or f'{doc.item_id or "doc"}_{info["id"]}'
    partial, is_version = _folder(folder, doc, info)
    req = {e: str(partial / f"{name}.{{frame}}.{e}") for e in formats}
    with kept_unless_stopped(partial, stopped):
        out = draw.render(where, f"frames {f0}-{f1} of {info['id']}", engine, scene, camera=info["camera"], renderer=renderer,
                          frames=[f0, f1], width=w, height=h, exposure=0, timeoutS=3600, **cycles,
                          progress=(lambda i, n, _=None: progress(i, n)) if progress else None, **req,
                          **({"passes": passes} if passes and "exr" in formats else {}))
    for e in formats:
        _renumber(partial, name, e, f0, FIRST)
    want = (f1 - f0 + 1) * len(formats)
    made = sorted(p for e in formats for p in partial.glob(f"{name}.*.{e}"))
    if len(made) != want or any(p.stat().st_size == 0 for p in made):      # fail loudly: the .partial stays
        raise RostrumError(codes.RENDER_FAILED, where, f"the frames of {info['id']}", f"came out as {len(made)} files, expected {want}",
                           hint=f"They are left in {partial}; nothing was listed as a version.")
    done = _finish(partial, is_version, _manifest(doc.item_id, doc, info, partial, renderer, (w, h),
                                                  list(range(f0, f1 + 1)), [p.name for p in made], FIRST,
                                                  out.get("channels")))
    return done, [done / p.name for p in made]
