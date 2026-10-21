"""A screen playing a 2D item's render (material emissionRender): each shot frame gets the 2D frame of the same moment,
held at the ends; a missing frame or no render is a loud error, never a blank screen."""
import json
from pathlib import Path

import pytest

from rostrum_core import RostrumError, project
from rostrum3d.material_scene import frames_for


def _project(tmp_path, numbers, fps=12):
    (tmp_path / "project.json").write_text(json.dumps({"items": [{"id": "ui", "kind": "2d"}]}), encoding="utf-8")
    part = project.begin_render(tmp_path, "ui")
    for n in numbers:
        (part / f"ui_main.{n}.png").write_bytes(b"png")
    project.finish_render(part, {"kind": "pictures", "frames": {"first": 1001, "last": 1003, "fps": f"{fps}/1", "start": 0.0}})
    return tmp_path


def test_frames_follow_time_and_hold_at_the_end(tmp_path):
    folder = _project(tmp_path, [1001, 1002, 1003])
    names = [Path(p).name for p in frames_for("m.emissionRender", "ui", folder, range(0, 8), 24)]
    assert names == ["ui_main.1001.png"] * 2 + ["ui_main.1002.png"] * 2 + ["ui_main.1003.png"] * 4


def test_missing_frame_and_no_render_are_loud(tmp_path):
    folder = _project(tmp_path, [1001, 1003])
    with pytest.raises(RostrumError, match="frame 1002"):
        frames_for("m.emissionRender", "ui", folder, range(0, 4), 24)
    with pytest.raises(RostrumError):
        frames_for("m.emissionRender", "nope", folder, range(0, 1), 24)
