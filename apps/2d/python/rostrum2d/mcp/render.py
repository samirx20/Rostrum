"""The one place the MCP tools reach the render engine (rostrum2d.engine), so swapping engines is one file.
Every engine failure becomes RENDER_FAILED naming what was being drawn; nothing is reported as done unless the file exists."""
from __future__ import annotations

from pathlib import Path

from rostrum_core import markers
from rostrum_core.errors import RostrumError, codes

from rostrum2d.scene import describe


def _fail(where: str, what: str, e: Exception) -> RostrumError:
    return RostrumError(codes.RENDER_FAILED, where, what, f"could not be drawn: {e}", hint="The engine's log path, if any, is in the message.")


def scene_of(doc, comp_id: str) -> dict:
    """The scene to draw; a text whose path layer is gone is refused here, in words (rostrum2d/follow.py)."""
    from rostrum2d import follow
    comp = next((c for c in doc.data.get("comps", []) if c["id"] == comp_id), None)
    if comp and (broken := follow.problems(comp)):
        raise RostrumError(codes.RENDER_FAILED, comp_id, "the composition", "can't be drawn: " + " ".join(broken))
    return describe(doc.data, comp_id, markers.times(doc.folder), doc.folder)


def stills(where: str, scene: dict, items: list[tuple[float, Path]], progress=None) -> None:
    """Draw each (time, png path). A failure names the frame and stops; earlier files stay."""
    from rostrum2d.engine import Engine
    fps = scene["comp"]["props"]["fps"]
    try:
        with Engine() as eng:
            eng.load(scene)
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


def video(where: str, scene: dict, mp4: Path, start: float, end: float, progress=None) -> dict:
    """Export to `<name>.partial.mp4`, then rename: a failed export never leaves a file under the final name."""
    from rostrum2d.engine import Engine
    part = mp4.with_name(mp4.stem + ".partial.mp4")
    try:
        with Engine() as eng:
            eng.load(scene)
            out = eng.video(part, start=start, end=end, progress=progress)
    except Exception as e:
        raise _fail(where, f"the video {mp4.name} (partial file, if any: {part})", e) from e
    if not part.is_file() or part.stat().st_size == 0:
        raise _fail(where, f"the video {mp4.name}", RuntimeError(f"no file at {part}"))
    part.replace(mp4)
    return out
