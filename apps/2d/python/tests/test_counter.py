"""A text that counts (text.counter; engine scene/counter.rs): the canvas's still and the export draw the same number
at the same time (one render path), its box follows the number shown, and a bad format is refused loudly."""
import pytest
from rostrum_core import Document, Who

from rostrum2d import KIND, run_source, settings
from rostrum2d.scene import describe

SRC = '''
comp("c", width=320, height=120, duration=1, fps=10, background="#000000")
text("n", body="words", font="Inter", size=40, x=160, y=60, figures="tabular lining")
'''
COUNT = {"op": "text.counter", "target": ["n"], "args": {"from": 0, "to": 1284000, "at": 0, "duration": 1, "ease": "linear",
                                                         "decimals": 1, "prefix": "$"}}


def _doc():
    d = Document.new(KIND)
    d.run_script("t.py", run_source(SRC, "t.py"))
    d.apply([COUNT], Who.agent("t"))
    return d


@pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")
def test_the_still_and_the_export_show_the_same_number_and_the_box_follows_it(tmp_path):
    from PIL import Image
    from rostrum2d import boxes
    from rostrum2d.engine import Engine
    d = _doc()
    assert len(d.history.changes) == 2                     # the script, then the counter: one change
    with Engine() as eng:
        eng.load(describe(d.data, "c"))
        eng.still(0.5, tmp_path / "still.png")
        eng.export({"start": 0.5, "end": 0.6, "images": str(tmp_path / "f-{frame}.png")})
        out = sorted(tmp_path.glob("f-*.png"))
        assert out, "the export wrote no frame"
        assert Image.open(tmp_path / "still.png").tobytes() == Image.open(out[0]).tobytes()
        eng.still(0.0, tmp_path / "zero.png")
        assert Image.open(tmp_path / "zero.png").tobytes() != Image.open(out[0]).tobytes()
    w0, w1 = (boxes.box(d.item("n"), t) for t in (0.0, 1.0))
    assert w1[2] - w1[0] > (w0[2] - w0[0]) + 40           # "$0.0" → "$1,284,000.0": the box grew with the digits


@pytest.mark.parametrize("args, why", [({"separator": "x"}, "separator"), ({"decimals": 9}, "decimals")])
def test_a_bad_format_is_refused(args, why):
    d = _doc()
    with pytest.raises(Exception, match=why):
        d.apply([{**COUNT, "args": {**COUNT["args"], **args}}], Who.agent("t"))
    with pytest.raises(Exception, match="countSeparator"):
        d.apply([{"op": "text.set", "target": ["n"], "args": {"countSeparator": "dots"}}], Who.agent("t"))
