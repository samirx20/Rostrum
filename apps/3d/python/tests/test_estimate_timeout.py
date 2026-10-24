"""The time probe never hangs (rule 6): an engine that never answers is stopped within the probe's budget, the error says
so plainly, and no engine process is left running. The "engine" is a real child process that reads nothing and says
nothing (python sleeping), so the wait is a real blocked pipe, as with a stalled rostrum3d-core."""
import sys
import time

import pytest
from rostrum_core.cache import Cache
from rostrum_core.errors import RostrumError

from rostrum3d import estimate_job
from rostrum3d.engine import Engine

SETTINGS = {"renderer": "cycles", "samples": 128, "denoise": True, "width": 640, "height": 360, "start": 0, "end": 0}


def test_a_probe_whose_engine_never_answers_stops_in_time_and_leaves_no_engine(tmp_path, monkeypatch):
    monkeypatch.setattr(estimate_job, "CACHE", Cache(tmp_path / "cache"))
    made = []

    def silent():
        made.append(e := Engine(exe=sys.executable, env=None, args=("-c", "import time; time.sleep(120)")))
        return e
    t0 = time.monotonic()
    with pytest.raises(RostrumError) as err:
        estimate_job.measure({"items": []}, {"id": "s", "camera": "cam"}, SETTINGS, "test", budget_s=2.0,
                             make_engine=silent, card=lambda pids: "")
    assert time.monotonic() - t0 < 4.0
    assert "ran over its 2 s budget" in err.value.problem and "engine was ended" in err.value.problem
    assert made and made[0].proc is not None and made[0].proc.poll() is not None      # its engine is gone
