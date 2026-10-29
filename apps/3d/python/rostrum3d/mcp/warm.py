"""Warm the engine while the agent reads: the first look of a session pays for starting the engine and Storm's (or the
Stylized look's) first frame, about a second. The server starts that work aside as it opens, on the open scene, so the
agent's first look (the one after its first script included) costs what every other look costs. Nothing is saved:
the picture goes to a temporary folder. Warming is a help; a failure is silent here and the look itself reports it."""
from __future__ import annotations

import tempfile
import threading
from pathlib import Path

from rostrum3d.compile import shot_info

from . import draw
from .shot import look_renderer

SIZE = (160, 90)


def warm(app) -> None:
    for doc in list(app.documents.values())[:1]:
        shots = doc.data.get("shots", [])
        info = dict(shot_info(doc.data, shots[0]["id"])) if shots else None
        if not info or not info.get("camera"):
            app.state.engine._ensure_running()          # still worth it: the process and its libraries
            return
        renderer = look_renderer({}, doc, [info])
        with tempfile.TemporaryDirectory(prefix="rostrum3d_warm_") as tmp:
            draw.render("warm", "the first frame", app.state.engine, draw.scene_of(doc, info["id"]), camera=info["camera"],
                        renderer=renderer, frame=info["start"], width=SIZE[0], height=SIZE[1], png=str(Path(tmp) / "warm.png"))


def start(app) -> threading.Thread:
    def run():
        try:
            warm(app)
        except Exception:                               # noqa: BLE001  a help only (see above)
            pass
    t = threading.Thread(target=run, name="rostrum3d-warm", daemon=True)
    t.start()
    return t
