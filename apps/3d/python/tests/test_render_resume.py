"""A stopped shot export keeps the frames it finished, and the same export again draws only the missing ones (mcp/resume.py);
a change to what is rendered starts afresh. (Critic 3d-final: a stopped export threw away ~130 frames, 20 minutes.)"""
import base64
from pathlib import Path

import pytest
from rostrum_core import Document, Who, live, project
from rostrum_core.errors import RostrumError

from rostrum3d import KIND, run_source
from rostrum3d.compile import describe, shot_info
from rostrum3d.mcp.render import DocView
from rostrum3d.mcp.sequence import sequence

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg==")

SRC = '''
cam = camera("cam", focalLength=50, z=3).aim((0, 0, 0))
mesh("ball", shape="sphere", radius=0.2)
shot("hero", name="Hero 01", camera=cam, fps=10, start=0, end=1)
'''


class Stopped(Exception):
    pass


class FakeEngine:
    """Draws a whole PNG per frame of `frames`, the way the engine names them; `stop_after` frames in all, it is stopped."""

    def __init__(self, stop_after=None):
        self.drawn, self.stop_after = [], stop_after

    def ensure_scene(self, scene):
        return True

    def render(self, progress=None, frames=None, png=None, **req):
        a, b = frames
        for i, f in enumerate(range(a, b + 1)):
            if self.stop_after is not None and len(self.drawn) >= self.stop_after:
                Path(png.replace("{frame}", f"{f:04d}") + ".partial").write_bytes(PNG[:20])     # a half-written file
                raise Stopped()
            Path(png.replace("{frame}", f"{f:04d}")).write_bytes(PNG)
            self.drawn.append(f)
            if progress:
                progress(i + 1, b - a + 1, {})
        return {"ok": True}


def _go(folder, doc, engine, stopped=None, **kw):
    info = shot_info(doc.data, "hero")
    said = []
    out = sequence("test", DocView.of(doc), info, describe(doc.data, "hero", folder), engine, (64, 36), ["png"], {"samples": 4},
                   folder, stopped=stopped, resumed=said.append, **kw)
    return out, said


def test_stopped_export_keeps_frames_and_restart_draws_only_the_rest(tmp_path):
    doc = Document.new(KIND, tmp_path, "product")
    live.keep(doc)
    doc.run_script("product.py", run_source(SRC, "product.py"), Who.agent("claude"))

    with pytest.raises(RostrumError, match="6 finished frames are kept"):
        _go(tmp_path, doc, FakeEngine(stop_after=6), stopped=lambda: True)
    kept = list((tmp_path / "renders" / "product").glob("v*.partial"))
    assert len(kept) == 1 and len(list(kept[0].glob("*.png"))) == 6           # the stop kept its 6 frames

    again = FakeEngine()
    seen = []
    (done, files), said = _go(tmp_path, doc, again, progress=lambda i, n: seen.append((i, n)))
    assert said == [6] and again.drawn == [6, 7, 8, 9]                       # only the 4 missing frames were drawn
    assert seen[-1] == (10, 10) and seen[0] == (7, 10)                       # kept frames count as done
    assert [f.name for f in files] == [f"product_hero.{1001 + i}.png" for i in range(10)]
    assert str(done) == project.renders(tmp_path, "product")[0]["path"] and not (done / "resume.json").exists()
    assert not list((tmp_path / "renders" / "product").glob("*.partial"))

    with pytest.raises(RostrumError):                                        # stopped again, then the scene changes:
        _go(tmp_path, doc, FakeEngine(stop_after=3), stopped=lambda: True)
    doc.run_script("more.py", run_source('mesh("box", shape="box")', "more.py"), Who.agent("claude"))
    fresh = FakeEngine()
    _, said = _go(tmp_path, doc, fresh)
    assert said == [0] and fresh.drawn == list(range(10))                   # its frames are not reused
