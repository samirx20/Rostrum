"""H40: an engine that never answers can't hang the app (a start once sat without a window): the request fails
loudly within its time limit, the stuck process is ended, and a retry gets a fresh one."""
import sys
import time

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="a .bat stands in for the engine")
def test_a_silent_engine_times_out_and_is_ended(tmp_path):
    from rostrum2d.engine import Engine, EngineError
    silent = tmp_path / "silent.bat"
    silent.write_text("@ping -n 4 127.0.0.1 >nul\n")      # reads nothing, says nothing (3 s, then gone)
    eng = Engine(silent)
    first = eng.pid
    t0 = time.monotonic()
    with pytest.raises(EngineError, match="gave no answer to measure in 1 s"):
        eng._request({"measure": {"items": []}}, timeout_s=1.0)
    assert time.monotonic() - t0 < 10 and eng.pid != first       # timed out, restarted once, timed out again
    eng.kill()
    eng.close()
