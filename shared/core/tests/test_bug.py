"""A bug says what failed (step, file), and a developer's log line can never fail the work (rostrum_core/bug.py)."""
import sys

from rostrum_core import bug


def test_a_closed_stderr_never_fails_the_work(monkeypatch, tmp_path):
    """agents-first-time b1: a scene-load log line on a stderr pipe whose reader had gone failed paint.stroke with a
    bare "OSError: [Errno 22] Invalid argument" at a random op."""
    class Gone:
        def write(self, _):
            raise OSError(22, "Invalid argument")
        flush = write
    monkeypatch.setattr(sys, "stderr", Gone())
    bug.note("2D scene sent whole")                                     # no raise
    monkeypatch.setattr(bug, "LOG_DIR", tmp_path)
    try:
        open(tmp_path / "missing" / "x.png", "rb")
    except OSError as e:
        err = bug.internal("op 3 of 9 (paint.stroke)", "paint.stroke", e)
    assert "x.png" in err.problem and "test_bug.py line" in err.problem and str(tmp_path) in err.hint
