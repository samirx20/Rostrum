"""The one place the MCP tools reach the engine (rostrum3d.engine), so swapping engines is one file.
Every engine failure becomes RENDER_FAILED naming what was being drawn; a restart of the engine is reported as a warning."""
from __future__ import annotations

from rostrum_core.errors import RostrumError, codes

from rostrum3d.compile import describe


def scene_of(doc, shot_id: str) -> dict:
    return describe(doc.data, shot_id, getattr(doc, "folder", None))


def engine_of(ctx):
    return ctx.app.state.engine


def call(where: str, what: str, engine, scene: dict, method: str, *args, **kw):
    """Send the scene if it changed, then run `engine.<method>`. Returns the engine's reply."""
    try:
        engine.ensure_scene(scene)
        return getattr(engine, method)(*args, **kw)
    except RostrumError:
        raise
    except Exception as e:
        raise RostrumError(codes.RENDER_FAILED, where, what, f"could not be drawn: {e}",
                           hint="The engine's log path, if any, is in the message.") from e


def render(where: str, what: str, engine, scene: dict, progress=None, step=None, **req) -> dict:
    return call(where, what, engine, scene, "render", progress=progress, **({"step": step} if step else {}), **req)
