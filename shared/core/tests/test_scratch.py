"""Scratch sweep: dead runs' old folders go; a running process's, a recent one and a non-pid name stay."""
import os
import subprocess
import sys
import time

from rostrum_core import scratch


def test_sweep(tmp_path):
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        dead = subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait()
        old = time.time() - 3 * 86400
        for name in (str(dead.pid), str(p.pid), "1999999990", "notapid"):
            d = tmp_path / name
            d.mkdir()
            os.utime(d, (old, old))
        (tmp_path / "1999999991").mkdir()                       # recent: stays
        assert scratch.sweep(tmp_path) == 2                     # the dead one and the id nobody has
        assert sorted(x.name for x in tmp_path.iterdir()) == sorted([str(p.pid), "notapid", "1999999991"])
    finally:
        p.kill()
        p.wait()
