"""A shot's frames as numbered pictures (png and/or exr), as one project render version: the one code path of the
render sheet's "the shot" (screen3d/export3d.py) and the Render page's queue (screen3d/queue.py). The frames are
drawn into `vNNN.partial/`, counted, renumbered to the hand-off numbering (FIRST = 1001), and only then finished with
a manifest; a failed or stopped render keeps its `.partial` folder with the frames it finished (never listed as a version),
and the same render asked for again continues there, drawing only the missing frames (mcp/resume.py).
"""
from __future__ import annotations

from pathlib import Path

from rostrum_core.errors import RostrumError, codes

from ..sim.compute import ready_for_render
from . import resume
from .render import FIRST, _finish, _manifest, _renumber, resumable_folder


def sequence(where: str, doc, info: dict, scene: dict, engine, size: tuple[int, int], formats: list[str], cycles: dict,
             folder=None, stem: str | None = None, progress=None, passes: list[str] | None = None, stopped=None,
             renderer: str = "cycles", resumed=None) -> tuple[Path, list[Path]]:
    """Frames info["start"]..info["end"] of the shot through its camera with Cycles (or `renderer`; `cycles`: that
    renderer's request settings, render_fields.engine_fields). `progress(done, total)` is called
    as frames land (kept frames count as done; it may raise to stop). `passes`: the EXR's extra layers (render_fields.PASSES; only with an exr),
    listed in the manifest's `exr`. `resumed(n)`: called once, before drawing, with the finished frames it continues from (0: none).
    Blocking: call it from a job. Returns (the finished folder, its files)."""
    f0, f1, (w, h) = info["start"], info["end"], size
    name = stem or f'{doc.item_id or "doc"}_{info["id"]}'
    passes = passes if passes and "exr" in formats else None
    key = sequence_key(scene, info, size, formats, cycles, passes, renderer)     # before the simulation is laid over it
    scene = ready_for_render(where, doc.data, info["id"], folder, scene)     # a falling thing: its simulation, computed first if needed
    partial, is_version = resumable_folder(folder, doc, info, key)
    where_of = {e: partial for e in formats}
    have = resume.finished(where_of, name, f0, f1, tidy=True)
    if resumed:
        resumed(len(have))
    req = {e: str(partial / f"{name}.{{frame}}.{e}") for e in formats}
    with resume.keeps_frames(partial, lambda: len(resume.finished(where_of, name, f0, f1)), stopped):
        out = resume.render_missing(where, f"frames {f0}-{f1} of {info['id']}", engine, scene, f0, f1, have, progress,
                                    camera=info["camera"], renderer=renderer, width=w, height=h, exposure=0, timeoutS=3600, **cycles,
                                    **req, **({"passes": passes} if passes else {}))
        got = resume.finished(where_of, name, f0, f1)
        if len(got) != f1 - f0 + 1:                                     # fail loudly: the .partial stays, its frames kept
            raise RostrumError(codes.RENDER_FAILED, where, f"the frames of {info['id']}", f"came out as {len(got)} whole frames, expected {f1 - f0 + 1}",
                               hint="Nothing was listed as a version.")
    out = out or {}                                                     # every frame was kept: no engine reply this time
    for e in formats:
        _renumber(partial, name, e, f0, FIRST)
    (partial / resume.RESUME).unlink(missing_ok=True)
    made = sorted(p for e in formats for p in partial.glob(f"{name}.*.{e}"))
    done = _finish(partial, is_version, _manifest(doc.item_id, doc, info, partial, renderer, (w, h),
                                                  list(range(f0, f1 + 1)), [p.name for p in made], FIRST,
                                                  out.get("channels")))
    return done, [done / p.name for p in made]



def sequence_key(scene: dict, info: dict, size, formats, cycles: dict, passes, renderer: str) -> str:
    """The hash a kept sequence is matched by (resume.key_of; `scene` as described, before its simulation is laid over it)."""
    return resume.key_of(scene, info, info["start"], info["end"], renderer, size, cycles, formats,
                         passes if passes and "exr" in formats else None)


def kept_count(folder, doc, info: dict, key: str, formats, stem: str | None = None) -> int:
    """How many finished frames the same sequence left to continue from (0: it starts afresh)."""
    name = stem or f'{doc.item_id or "doc"}_{info["id"]}'
    kept = resume.find(folder, doc.item_id, f'{doc.item_id or "doc"}_{info["id"]}', key)
    return len(resume.finished({e: kept for e in formats}, name, info["start"], info["end"])) if kept else 0
