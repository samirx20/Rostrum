"""A scripted run (--step, no --shot) ends once its steps are done: an export writes its whole file and the process exits
on its own (it used to wait forever); a failing step exits nonzero."""
import os
import re
import subprocess
import sys
from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "main.py"


def run(step, home):
    env = {**os.environ, "ROSTRUM_SCRIPTED_HOME": str(home)}      # the test's own scratch home: it outlives the run
    return subprocess.run([sys.executable, str(MAIN), "--sample", "--step", step], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120, env=env)     # a hang is a TimeoutExpired, loud


def test_export_step_exits_with_a_complete_file(tmp_path):
    r = run("export gif", tmp_path)
    assert r.returncode == 0, r.stderr
    path = Path(re.search(r"^export gif: (.+\.gif) \[", r.stdout, re.M).group(1))
    data = path.read_bytes()
    assert data[:6] in (b"GIF87a", b"GIF89a") and data[-1:] == b";"     # header and trailer: the file is whole


def test_failed_step_exits_nonzero(tmp_path):
    assert run("export nonsense", tmp_path).returncode == 3
