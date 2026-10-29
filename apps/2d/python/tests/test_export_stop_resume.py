"""An MP4 export stopped part-way (run_stop) keeps the segments it finished, and exporting again draws only the rest
(the engine saves each part's file as it draws, then it is cut into its segments: export_cache.py `_draw`, `_parts`): Undertow, 2026-10-29, a re-export after a
stop at frame 309 of 900 started again from frame 0. No engine or FFmpeg: the drawing and the join stand in."""
import contextlib
from pathlib import Path

import pytest

from rostrum2d.io import export as io_export
from rostrum2d.io import readback
from rostrum2d.mcp import export_cache

SCENE = {"comp": {"type": "comp", "id": "c", "props": {"width": 64, "height": 36, "fps": 10, "duration": 8.0}, "layers": []}}
SETTINGS = {"start": 0.0, "end": 8.0}


class Stopped(Exception):
    pass


def _fakes(monkeypatch, tmp_path, drawn: list, stop_at: float | None):
    """Drawing records each request's (start, end) and saves each segment whose frames are all drawn; when `stop_at` is
    inside a request it stops there as run_stop does (the segments finished before it saved, the one it was in not)."""
    monkeypatch.setattr(export_cache, "folder", lambda: tmp_path / "cache")
    from rostrum2d import engine_export
    monkeypatch.setattr(engine_export, "PART_FRAMES", 40)                # parts of 4 s: two 2 s segments each
    monkeypatch.setattr(export_cache, "_split", lambda run, cuts, into: [Path(f).write_text("seg") for f in into] and True)

    def export(eng, fmt, part, alpha, depth, t0, t1, progress, quality, bitrate, saves):
        drawn.append((round(t0, 3), round(t1, 3)))
        assert Path(saves[-1][1]) == Path(part)
        for end, file in saves:
            if stop_at is not None and t0 + end / 10 > stop_at:
                raise Stopped(f"stopped at {stop_at} s")
            Path(file).write_text(f"to {end}")
        return {"frames": round((t1 - t0) * 10)}

    monkeypatch.setattr(io_export, "export", export)
    monkeypatch.setattr(export_cache, "_join", lambda files, target: target.write_text("joined"))
    monkeypatch.setattr(readback, "check", lambda *a, **k: {})            # the joined file's read-back (no FFmpeg here)


@contextlib.contextmanager
def _engine():
    class Eng:
        def load(self, scene):
            pass

        def kill(self):
            pass
    yield Eng()


def test_a_stopped_export_keeps_its_finished_segments(tmp_path, monkeypatch):
    drawn: list = []
    _fakes(monkeypatch, tmp_path, drawn, stop_at=5.0)                 # stopped in the second part (4-8 s)
    with pytest.raises(Stopped):
        export_cache.export(SCENE, SETTINGS, tmp_path / "a.mp4", None, _engine)
    assert drawn == [(0.0, 8.0)]                                       # one request for the whole film
    kept = [f for f in (tmp_path / "cache").glob("*.mp4") if ".partial" not in f.name]
    assert len(kept) == 2 and not list((tmp_path / "cache").glob("*.partial*"))   # the first part's two segments, kept; no part file left

    again: list = []
    _fakes(monkeypatch, tmp_path, again, stop_at=None)
    facts = export_cache.export(SCENE, SETTINGS, tmp_path / "b.mp4", None, _engine)
    assert again == [(4.0, 8.0)]                                       # from where it stopped, not frame 0
    assert (facts["segments"]["reused"], facts["segments"]["drawn"]) == (2, 2)
