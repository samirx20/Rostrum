"""A 3D render layer follows its item's newest render (or the pinned one), keeps the transparency, and says loudly when
there is nothing to show (render3d.py)."""
import json

import numpy as np
import OpenEXR
import pytest
from PIL import Image
from rostrum_core import RostrumError, project

from rostrum2d import render3d


def _render(folder, alpha):
    part = project.begin_render(folder, "product")
    px = np.zeros((8, 8, 4), np.float32)
    px[..., 1], px[..., 3] = 0.5 * alpha, alpha                     # premultiplied green
    OpenEXR.File({"type": OpenEXR.scanlineimage}, {"RGBA": px}).write(str(part / "product_hero.1001.exr"))
    return project.finish_render(part, {"kind": "pictures", "frames": {"fps": "24/1"}, "source": {"history_entry": 1}})


def test_follows_newest_and_fails_loudly(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "product.trd").write_text(json.dumps({"doc": {"name": "Product"}}), encoding="utf-8")
    layer = {"id": "hero", "type": "render3d", "item": "product", "version": 0}
    with pytest.raises(RostrumError, match="not rendered yet"):
        render3d.find(layer, tmp_path)
    _render(tmp_path, 1.0)
    _render(tmp_path, 0.5)
    assert render3d.find(layer, tmp_path)["version"] == 2
    assert render3d.find({**layer, "version": 1}, tmp_path)["version"] == 1
    with pytest.raises(RostrumError, match="no render v007"):
        render3d.find({**layer, "version": 7}, tmp_path)
    r = render3d.find(layer, tmp_path)
    png = render3d.picture(tmp_path / "renders" / "product" / "v002" / r["exrs"][0], 4, 4, "stretch")
    assert np.asarray(Image.open(png))[..., 3].mean() == pytest.approx(128, abs=1)    # half see-through, kept


def test_out_of_date_is_by_content_not_by_steps(tmp_path):
    from rostrum_core import storage
    (tmp_path / "docs").mkdir()
    trd, doc = tmp_path / "docs" / "product.trd", {"name": "Product", "light": 1}

    def save(d):
        trd.write_text(json.dumps({"doc": d}), encoding="utf-8")
    render = {"item": "product", "source_seq": 1, "source_hash": storage.doc_hash(doc)}
    save(doc)
    assert not render3d.is_stale(render, tmp_path)
    save({**doc, "light": 2})                                       # changed …
    assert render3d.is_stale(render, tmp_path)
    save(doc)                                                       # … and changed back: same content, not stale
    assert not render3d.is_stale(render, tmp_path)
