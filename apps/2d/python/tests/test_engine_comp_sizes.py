"""E10: one running engine draws comps of different sizes one after another (the app switches comps all the time).
A larger comp loaded after a smaller one used to fail its first frame on the GPU (GL error 0x0501): the new comp's
painter made a second GL context beside the old one (painter.rs `into_gl`)."""
import os

import pytest
from rostrum_core import Document

from rostrum2d import KIND, run_source
from rostrum2d.scene import describe

pytestmark = pytest.mark.skipif(not os.environ.get("ROSTRUM2D_ENGINE"), reason="needs a built engine (ROSTRUM2D_ENGINE)")
SRC = '''
comp("small", width=64, height=36, duration=1, fps=10, background="#204060")
shape("a", w=20, h=20, fill="#ff0000", x=32, y=18)
comp("big", width=1920, height=1080, duration=1, fps=10, background="#204060")
shape("b", w=600, h=600, fill="#ff0000", x=960, y=540)
'''


def test_small_then_big_then_small_each_frame_drawn():
    from rostrum2d.engine import Engine
    d = Document.new(KIND)
    d.run_script("t.py", run_source(SRC, "t.py"))
    with Engine() as eng:
        for comp, (w, h) in [("small", (64, 36)), ("big", (1920, 1080)), ("small", (64, 36))]:
            eng.load(describe(d.data, comp))
            view, pw, ph, stride = eng.pixels(0.5)
            px = bytes(view)
            view.release()
            assert (pw, ph) == (w, h), comp
            mid = (h // 2) * stride + (w // 2) * 4
            assert px[mid:mid + 4] == b"\xff\x00\x00\xff", comp   # the shape drawn, in the middle
            assert px[0:3] == b"\x20\x40\x60", comp                # the background in the corner
