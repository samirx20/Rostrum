"""Dragging a keyed copy (Turn into keys on falling copies) must move it: the drop keys the moved field at the playhead's
frame, so the copy is seen where it was dropped there (a plain copies.hold would be overridden by its keys: a drag that
does nothing). No viewport or engine: the gizmo's drop calls on stand-ins."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document, Who  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.compile import describe  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from screen3d.copies_gizmo import CopyGizmo, keyed_now  # noqa: E402

SAM = Who.person()
SRC = '''
cam = camera("cam", z=3)
bud = mesh("bud", shape="sphere", radius=0.05)
copies("buds", bud, layout="line", count=3)
shot("s", camera=cam, fps=10, start=0, end=2)
'''


def test_dropping_a_keyed_copy_keys_it_at_the_playhead():
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SRC, "s.py"))
    doc.apply([{"op": "copies.key", "target": ["buds"], "args": {"copy": 1, "prop": p, "t": t, "v": v}}
               for p in ("x", "y", "z", "rx", "ry", "rz") for t, v in ((0.0, 0.0), (1.0, 1.0))], SAM)
    frame, scene = 5, describe(doc.data, "s")
    now = keyed_now(scene, "buds", 1, frame)
    assert 0.0 < now["y"] < 1.0                                          # between its keys at the playhead

    g = SimpleNamespace(vp=SimpleNamespace(sent=lambda: (scene, {})), bridge=SimpleNamespace(frame=frame))
    c = {"it": doc.item("buds"), "copy": 1, "v": {**now, "sx": 1.0}}
    calls = CopyGizmo._copy_calls(g, c, {**now, "y": 2.0, "s": 1.0})      # dragged up to y = 2
    assert [call["op"] for call in calls] == ["copies.key"]
    doc.apply(calls, SAM)
    assert keyed_now(describe(doc.data, "s"), "buds", 1, frame)["y"] == pytest.approx(2.0)
