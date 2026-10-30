"""The one place the MCP tools reach the render engine (rostrum2d.engine), so swapping engines is one file.
Every engine failure becomes RENDER_FAILED naming what was being drawn; nothing is reported as done unless the file exists."""
from __future__ import annotations

import time
from pathlib import Path

from rostrum_core import markers
from rostrum_core.errors import RostrumError, codes

from rostrum2d.scene import describe

from . import edge_cut, warm


SLOW_PICTURES_S = 5.0


def _fail(where: str, what: str, e: Exception) -> RostrumError:
    return RostrumError(codes.RENDER_FAILED, where, what, f"could not be drawn: {e}", hint="The engine's log path, if any, is in the message.")


def scene_of(doc, comp_id: str, span: tuple[float, float] | None = None, frames: list[int] | None = None) -> dict:
    """The scene to draw; a text whose path layer is gone is refused here, in words (rostrum2d/follow.py).
    `span`: the (first, last) seconds that will be drawn, when not the whole composition (scene.describe); `frames`:
    only these frame numbers in it will be drawn (a contact sheet)."""
    return scene_later(doc, comp_id, span, frames)()


def scene_later(doc, comp_id: str, span: tuple[float, float] | None = None, frames: list[int] | None = None):
    """scene_of in two halves: its refusals now, and a call `(progress, stopped) -> scene` that describes the document
    as it is now (a document is never changed in place: holding its data is the snapshot), making the painted pictures
    first: minutes for a painted piece, so an export runs it in its job, never on the screen's thread (2D final critic)."""
    from rostrum2d import follow
    comp = next((c for c in doc.data.get("comps", []) if c["id"] == comp_id), None)
    if comp and (broken := follow.problems(comp)):
        raise RostrumError(codes.RENDER_FAILED, comp_id, "the composition", "can't be drawn: " + " ".join(broken))
    data, times, folder = doc.data, markers.times(doc.folder), doc.folder

    def make(progress=None, stopped=None) -> dict:
        t0 = time.perf_counter()
        scene = describe(data, comp_id, times, folder, span, frames=frames, progress=progress, stopped=stopped)
        spent = time.perf_counter() - t0
        if spent >= SLOW_PICTURES_S:    # the painted pictures are made here, the first time (kept by content afterwards): say what it cost
            scene["warnings"] = [*scene.get("warnings", []), f"Making the painted pictures took {spent:.0f} s: strokes are drawn the first time a look or export needs "
                                 "them, not when a script adds them. They are kept, so the next look at the same paint is quick."]
        if span and span[0] == span[1] and comp and not frames:      # one frame (look_frame): a subject cut by the frame edge is said in its reply
            try:
                scene["warnings"] = [*scene.get("warnings", []), *edge_cut.warnings_at(data, played(comp, times), span[0])]
            except Exception as e:      # noqa: BLE001  (the look still stands; the check's failure is said)
                scene["warnings"] = [*scene.get("warnings", []), f"(The frame-edge check could not run: {e}.)"]
        return scene
    return make


def look_scene(doc, comp_id: str, at: float | None = None, times: list[float] | None = None) -> dict:
    """What the looks draw (look_frame, sheets, run_script's look, the review): the whole composition, described again
    only where the document changed (warm.py), its refusals first as scene_of's. `at`: one frame's look, whose reply
    names a subject cut by the frame edge then. `times` (or `at`): the only moments drawn with it, so only their
    Drawn so far pictures are made (warm.scene); none: every one."""
    from rostrum2d import follow
    comp = next((c for c in doc.data.get("comps", []) if c["id"] == comp_id), None)
    if comp and (broken := follow.problems(comp)):
        raise RostrumError(codes.RENDER_FAILED, comp_id, "the composition", "can't be drawn: " + " ".join(broken))
    scene = warm.scene(doc, comp_id, (comp or {}).get("duration", 5.0), times if times is not None else None if at is None else [at])
    if at is None or comp is None:
        return scene
    try:
        cut = edge_warnings(doc.data, played(comp, markers.times(doc.folder) if doc.folder else None), at)
    except RostrumError as e:       # a marker that is gone: the drawing says so; the check names its own failure
        cut = [f"(The frame-edge check could not run: {e.line()})"]
    return {**scene, "warnings": [*scene.get("warnings", []), *cut]} if cut else scene


def played(comp: dict, times: dict | None) -> dict:
    """The composition as it plays: keys and layers timed on a shared marker in composition seconds (retime.py). The
    frame-edge check reads boxes from keys, and one key on a marker ("#pay+0.3") switched it off for every look."""
    from rostrum2d import retime
    return retime.timed(comp, times, comp.get("fps", 30))


def edge_warnings(doc_data: dict, comp: dict, at: float) -> list[str]:
    """One frame's look: a subject cut by the frame edge at `at`, in words (edge_cut.py); its own failure said, never raised.
    `comp` as it plays (played(), or pick.doc_and_comp's)."""
    try:
        return edge_cut.warnings_at(doc_data, comp, at)
    except Exception as e:      # noqa: BLE001  (the look still stands; the check's failure is said)
        return [f"(The frame-edge check could not run: {e}.)"]


def stills(where: str, scene: dict, items: list[tuple[float, Path]], progress=None) -> None:
    """Draw each (time, png path). A failure names the frame and stops; earlier files stay."""
    fps = scene["comp"]["props"]["fps"]
    try:
        with warm.engine(scene) as eng:
            for i, (t, png) in enumerate(items):
                try:
                    eng.still(t, png)
                except Exception as e:
                    raise _fail(where, f"frame {round(t * fps)} ({t:.3f} s)", e) from e
                if progress:
                    progress(i + 1, len(items))
    except RostrumError:
        raise
    except Exception as e:
        raise _fail(where, "the engine", e) from e


FAST_PNG = 1       # zlib level of a look's PNG: the same pixels (lossless), written ~4x quicker than PIL's default 6


def small_stills(where: str, scene: dict, items: list[tuple[float, Path]], width: int, progress=None, samples: int | None = None,
                 rgb: bool = False) -> list[tuple[int, int]] | None:
    """Draw each (time, png path) `width` px wide: the same frame drawn smaller by the engine (Engine.pixels' scale, as
    the canvas plays), not a full-size frame shrunk after; a sheet's tiles cost a fraction. `samples`: motion-blur steps
    (1: preview quality, look_quality.py; None: the composition's, as the export). Full width at final quality: stills
    (returns None then; else each picture's size). `rgb`: written without alpha, as the sheets show a look (one PNG
    write: the look's own file, not a copy of a raw one)."""
    from PIL import Image
    fps, comp_w = scene["comp"]["props"]["fps"], scene["comp"]["props"]["width"]
    if width >= comp_w and samples is None:
        return stills(where, scene, items, progress)
    sizes = []
    try:
        with warm.engine(scene) as eng:
            for i, (t, png) in enumerate(items):
                try:
                    view, w, h, stride = eng.pixels(t, samples, scale=min(1.0, width / comp_w))
                    data = bytes(view)                   # copied out: the engine's memory is reused next frame
                    view.release()
                    img = Image.frombuffer("RGBA", (w, h), data, "raw", "RGBA", stride, 1)
                    (img.convert("RGB") if rgb else img).save(png, "PNG", compress_level=FAST_PNG)
                    sizes.append((w, h))
                except Exception as e:
                    raise _fail(where, f"frame {round(t * fps)} ({t:.3f} s)", e) from e
                if progress:
                    progress(i + 1, len(items))
    except RostrumError:
        raise
    except Exception as e:
        raise _fail(where, "the engine", e) from e
    return sizes


def area_still(where: str, scene: dict, t: float, area, width: int, png: Path, samples: int | None = None) -> tuple[int, int]:
    """Only `area` [x, y, w, h] (comp px) of the frame at `t`, drawn by the engine at `width` px wide (sharp: a zoom,
    not a crop of a small picture), as `png`. Returns its size. `samples` as small_stills'."""
    from PIL import Image
    x, y, w, h = (float(v) for v in area)
    try:
        with warm.engine(scene) as eng:
            view, pw, ph, stride = eng.pixels(t, samples, view={"x": x, "y": y, "w": w, "h": h, "scale": width / w})
            data = bytes(view)
            view.release()
            Image.frombuffer("RGBA", (pw, ph), data, "raw", "RGBA", stride, 1).save(png, "PNG", compress_level=FAST_PNG)
            return pw, ph
    except RostrumError:
        raise
    except Exception as e:
        raise _fail(where, f"the area {[x, y, w, h]} at {t:.3f} s", e) from e


def video(where: str, scene: dict, mp4: Path, start: float, end: float, progress=None, quality=None, bitrate=None, on_stop=None) -> dict:
    """Export to `<name>.partial.mp4`, then rename: a failed export never leaves a file under the final name. `on_stop`: a
    job's on_cancel, given the engine's end (run_stop ends the engine at once, even mid-frame)."""
    from rostrum2d.engine import Engine
    from . import export_cache
    part = mp4.with_name(mp4.stem + ".partial.mp4")
    try:            # only the segments whose layers changed since the last export are drawn again (export_cache.py)
        out = export_cache.export(scene, {"start": start, "end": end, "quality": quality, "bitrate": bitrate}, part, progress, Engine, on_stop)
    except Exception as e:
        raise _fail(where, f"the video {mp4.name} (partial file, if any: {part})", e) from e
    if not part.is_file() or part.stat().st_size == 0:
        raise _fail(where, f"the video {mp4.name}", RuntimeError(f"no file at {part}"))
    part.replace(mp4)
    return out
