"""The project's own tip pictures: a stroke names the item, so a moved project still paints the same, and a stroke
whose item is gone fails loudly, naming it."""
import shutil

import numpy as np
import pytest
from PIL import Image

from rostrum_core.cache import Cache
from rostrum_core.errors import RostrumError
from rostrum_paint import brush, fields, library


def _paint(tip_id):
    layer = np.zeros((64, 96, 4), np.float32)
    brush.stamp_stroke(layer, [[10, 32], [86, 32]], (0.1, 0.1, 0.1), 30, "round", texture=tip_id, seed=3)
    return layer


def test_loaded_tip_survives_a_move_and_a_missing_one_names_itself(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "CACHE", Cache(tmp_path / "cache"))
    monkeypatch.setattr(library, "_arrays", {})
    pic = tmp_path / "star.png"
    y, x = np.mgrid[-1:1:40j, -1:1:40j]
    Image.fromarray(((np.hypot(x, y) > 0.3 + 0.4 * np.abs(np.sin(2.5 * np.arctan2(y, x)))) * 255).astype(np.uint8)).save(pic)
    first = tmp_path / "one"
    first.mkdir()
    row = library.load(first, pic, "tip", "Star")
    assert row["id"] in [c["value"] for c in next(p for p in fields.BRUSH if p.name == "texture").choices()]
    before = _paint(row["id"])
    assert before[..., 3].max() > 0.5

    moved = tmp_path / "two"
    shutil.move(first, moved)
    monkeypatch.setattr(library, "CACHE", Cache(tmp_path / "cache2"))   # nothing kept: read again from the moved project
    monkeypatch.setattr(library, "_arrays", {})
    library.use_project(moved)
    assert np.array_equal(_paint(row["id"]), before)

    (tmp_path / "other").mkdir()
    library.use_project(tmp_path / "other")          # a project without that item
    with pytest.raises(RostrumError, match=row["id"]):
        _paint(row["id"])
    library.use_project(None)
