"""An engine that stops answering mid-export fails the export loudly within the frame limit, naming where it stopped,
and is ended (engine.py FRAME_LIMIT_S). p1, 2026-10-25: three whole-piece renders hung for good with no word."""
import subprocess
import sys
import time

import pytest

from rostrum2d import engine as engine_mod
from rostrum2d.engine import Engine, Stuck

FAKE = r"""
import json, sys, time
for line in sys.stdin:
    req = json.loads(line)
    if "export" in req:
        for i in (1, 2):
            print(json.dumps({"progress": i, "of": 30, "elapsedS": 0.1 * i, "leftS": 1.0}), flush=True)
        time.sleep(600)                               # stuck on the third frame
    else:
        print(json.dumps({"ok": True}), flush=True)
"""


def test_a_stuck_export_fails_loudly_naming_the_frame(tmp_path, monkeypatch):
    fake = tmp_path / "fake_engine.py"
    fake.write_text(FAKE)
    real = subprocess.Popen
    monkeypatch.setattr(engine_mod.subprocess, "Popen", lambda args, **kw: real([sys.executable, str(fake)], **kw))
    monkeypatch.setattr(engine_mod, "FRAME_LIMIT_S", 1.5)
    eng = Engine(exe=tmp_path / "fake_engine.py")
    try:
        eng.scene = {"comp": {"props": {"fps": 30, "duration": 2.0, "width": 64, "height": 64}}}
        t0 = time.monotonic()
        with pytest.raises(Stuck, match=r"after 2 of 30 frames: stuck at frame 32 \(1\.07 s\)"):
            eng.export({"start": 1.0, "end": 2.0, "encode": {"program": "x", "args": []}})
        assert time.monotonic() - t0 < 10
        assert eng.proc.wait(5) is not None           # the stuck engine was ended
    finally:
        if eng.proc.poll() is None:
            eng.proc.kill()
