"""S27 H1: an engine that dies is started again with the scene, the frame still comes and the person is told once;
one that dies again right away is not retried, and says so in one sentence. Cancel's kill is never restarted."""
import os

import pytest
from rostrum_core import Document

from rostrum2d import KIND, run_source
from rostrum2d.scene import describe

pytestmark = pytest.mark.skipif(not os.environ.get("ROSTRUM2D_ENGINE"), reason="needs a built engine (ROSTRUM2D_ENGINE)")
SRC = '''
comp("c", width=64, height=36, duration=1, fps=10, background="#204060")
shape("box", w=20, h=20, fill="#ff7a59", x=32, y=18)
'''


def _scene():
    d = Document.new(KIND)
    d.run_script("t.py", run_source(SRC, "t.py"))
    return describe(d.data)


def _die(eng):
    eng.proc.kill()
    eng.proc.wait()


def test_a_dead_engine_restarts_once_then_gives_up(tmp_path):
    from rostrum2d.engine import GAVE_UP, RESTARTED, Engine, EngineError
    with Engine() as eng:
        eng.load(_scene())
        first = eng.pid
        _die(eng)
        eng.still(0.5, tmp_path / "a.png")                     # drawn by a new engine, the scene loaded again
        assert eng.pid != first and (tmp_path / "a.png").is_file() and eng.notice == RESTARTED
        _die(eng)
        with pytest.raises(EngineError) as e:
            eng.still(0.5, tmp_path / "b.png")
        assert str(e.value) == GAVE_UP and e.value.plain
        with pytest.raises(EngineError, match="stopped twice"):    # stays stopped: no restart loop
            eng.still(0.5, tmp_path / "c.png")


def test_a_cancelled_engine_is_not_restarted(tmp_path):
    from rostrum2d.engine import Engine, EngineError
    with Engine() as eng:
        eng.load(_scene())
        eng.kill()
        with pytest.raises(EngineError, match="on purpose"):
            eng.still(0.5, tmp_path / "a.png")
