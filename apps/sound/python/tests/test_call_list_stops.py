"""What agents rely on: a call list stops at the first failed step, so a render never runs on a document the failed
script did not change, and the output says which step failed and which were not run."""
import json
import subprocess
import sys
from pathlib import Path

from rostrum_core import Document

from rostrum_sound import KIND

SESSION = Path(__file__).resolve().parents[1] / "devtools" / "mcp_session.py"


def test_a_failed_script_stops_the_calls_after_it(tmp_path):
    Document.new(KIND, folder=str(tmp_path), item="cue").save()
    calls = tmp_path / "calls.json"
    calls.write_text(json.dumps([{"tool": "run_script", "arguments": {"source": "this is not python ("}},
                                 {"tool": "render_mix", "arguments": {}}]), encoding="utf-8")
    run = subprocess.run([sys.executable, str(SESSION), "--folder", str(tmp_path), str(calls)],
                         capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert run.returncode == 1, run.stderr
    assert "STOPPED: step 1 (run_script) failed. NOT run: 2. render_mix" in run.stdout
    assert "--- 2." not in run.stdout
