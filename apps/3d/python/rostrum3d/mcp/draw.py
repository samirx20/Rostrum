"""The one place the MCP tools reach the engine (rostrum3d.engine), so swapping engines is one file.
Every engine failure becomes RENDER_FAILED naming what was being drawn; a restart of the engine is reported as a warning."""
from __future__ import annotations

from rostrum_core.errors import RostrumError, codes

from rostrum_core.cache import CACHE
from rostrum3d.compile import describe


def scene_of(doc, shot_id: str) -> dict:
    """The shot's compiled scene, built once per state of the document: a second look at the same scene (another frame, a
    sheet after run_script's look) reuses it. Built again when the document changes (every change is a new tree and a new
    seq) or this program stores something in the cache (a simulation's result, laid over the scene). Callers never change
    it in place (a look from a view or a light copies the items list first)."""
    folder = getattr(doc, "folder", None)
    seen = getattr(doc, "_scenes", None)
    if seen is None:
        try:
            seen = doc._scenes = {}
        except AttributeError:                                   # a stand-in without attributes: built every time
            return describe(doc.data, shot_id, folder)
    stamp = (doc.data, getattr(doc, "seq", None), CACHE.puts)
    hit = seen.get((shot_id, str(folder)))
    if hit and hit[0][0] is stamp[0] and hit[0][1:] == stamp[1:]:
        return hit[1]
    scene = describe(doc.data, shot_id, folder)
    seen.clear()                                                 # one state kept: the newest
    seen[(shot_id, str(folder))] = (stamp, scene)
    return scene


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
