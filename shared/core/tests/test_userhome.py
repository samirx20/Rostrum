"""A scripted run (--shot ...) keeps its settings and Open recent out of the person's home; two writers don't collide."""
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from rostrum_core import userhome
from rostrum_core.storage import write_atomic

ROOT = Path(__file__).resolve().parents[3]
CODE = ("import sys; from screen2d import recent; from rostrum2d import settings;"
        "recent.add(sys.argv[1], 'main'); print(settings.settings_path())")


def test_scripted_run_leaves_the_real_recent_list_alone(tmp_path):
    real = tmp_path / "home"
    (real / ".rostrum" / "2d").mkdir(parents=True)
    real_file = real / ".rostrum" / "2d" / "settings.json"
    real_file.write_text(json.dumps({"recent": [{"folder": "C:/mine", "item": "main"}]}), encoding="utf-8")
    before = real_file.read_bytes()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ROSTRUM_", "PYTEST"))}
    env.update(HOME=str(real), USERPROFILE=str(real), ROSTRUM_REAL_HOME="", PYTHONPATH=os.pathsep.join(sys.path))   # the same packages this test sees
    r = subprocess.run([sys.executable, "-c", CODE, str(tmp_path / "throwaway"), "--shot"], env=env,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert real_file.read_bytes() == before                      # the person's list is untouched
    assert "scripted run (--shot)" in r.stderr and "rostrum-run-" in r.stdout


def test_two_writers_never_share_a_temp_name(tmp_path):
    f = tmp_path / "a.json"
    errors = []

    def go(n):
        try:
            for i in range(30):
                with userhome.locked(f):
                    write_atomic(f, json.dumps({"n": n, "i": i}))
        except Exception as e:                                   # noqa: BLE001
            errors.append(e)
    ts = [threading.Thread(target=go, args=(n,)) for n in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors and json.loads(f.read_text())["i"] == 29
