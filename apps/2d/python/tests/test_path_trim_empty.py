"""FRICTION A1-2: a path whose drawn part is empty (trimEnd 0, or trimStart = trimEnd) draws nothing, round caps
included; the first drawn bit of a round-cap draw-on is its cap (shape-and-path-animation.md › Draw on)."""
import pytest
from rostrum_core import Document

from rostrum2d import KIND, run_source, settings
from rostrum2d.scene import describe

SRC = '''comp("film", width=400, height=200, duration=4, background="#ffffff")
a = path("a", d="M50 50 L350 50", fill="none", stroke=True, strokeColor="#000000", strokeWidth=16, cap="round")
a.key("trimEnd", {1: (0, "easeInOut"), 3: 1})
path("b", d="M50 120 L350 120", fill="none", stroke=True, strokeColor="#000000", strokeWidth=16, cap="round", trimStart=0.5, trimEnd=0.5)
path("c", d="M50 170 L350 170", fill="none", stroke=True, strokeColor="#000000", strokeWidth=16, cap="square", trimEnd=0)
'''


@pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")
def test_an_empty_trim_draws_no_cap(tmp_path):
    from PIL import Image
    from rostrum2d.engine import Engine
    d = Document.new(KIND)
    d.run_script("t.py", run_source(SRC, "t.py"))
    with Engine() as eng:
        eng.load(describe(d.data, "film"))
        for t, dark in ((0.5, False), (1.0, False), (1.05, True)):
            eng.still(t, tmp_path / "f.png")
            px = Image.open(tmp_path / "f.png").convert("L")
            assert (px.getextrema()[0] < 128) is dark, f"at {t} s"
