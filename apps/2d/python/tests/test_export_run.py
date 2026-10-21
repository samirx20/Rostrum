"""A failed export is loud and leaves nothing under the final name (a person or an agent would open a broken file otherwise)."""
from pathlib import Path

import pytest
from rostrum_core.errors import RostrumError

from rostrum2d.engine import EngineError
from rostrum2d.mcp import exporting

SCENE = {"comp": {"id": "c", "props": {"width": 32, "height": 16, "fps": 10, "duration": 1.0}}}


class DyingEngine:
    scene = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def load(self, scene):
        self.scene = scene

    def _request(self, req, **kw):
        if "export" in req:
            if "file" in req:
                Path(req["file"]).write_bytes(b"half a file")      # the encoder wrote something, then died
            raise EngineError("encoder died")
        return {}


@pytest.mark.parametrize("fmt, name", [("webm", "a.webm"), ("gif", "a.gif"), ("png", "seq")])
def test_failed_export_leaves_no_final_file(tmp_path, fmt, name):
    s = exporting.settings("t", fmt, 1.0)
    with pytest.raises(RostrumError, match="encoder died"):
        exporting.run("t", SCENE, fmt, s, out=tmp_path / name, engine_factory=DyingEngine)
    assert not (tmp_path / name).exists()


def test_a_setting_that_does_not_apply_is_refused():
    with pytest.raises(RostrumError, match="transparency"):
        exporting.settings("t", "mp4", 1.0, alpha=True)
    with pytest.raises(RostrumError, match="bit depth|bits"):
        exporting.settings("t", "gif", 1.0, depth=16)
