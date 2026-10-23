"""My brushes (rostrum2d/brushes.py): a saved brush gives back exactly the settings it was saved with (colour and
seed left out), rename keeps them, delete takes the file too, and a setting that isn't one is refused loudly. Two
brushes with the same settings stay two; an H56 file (settings alone) still loads; a brush kept in the person's
library reaches another project with its loaded tip picture. (pytest runs get a scratch library: userhome.)"""
import json
import pytest
from rostrum2d import brushes
from rostrum_core.errors import RostrumError
from rostrum_paint.fields import brush_defaults


def test_save_round_trips_rename_and_delete(tmp_path):
    values = {**brush_defaults(), "brush": "bristle", "size": 31.0, "hardness": 0.6, "follow": False, "angle": 30.0}
    b = brushes.save(tmp_path, "My oil", values, ["project"])
    [got] = brushes.saved(tmp_path)
    assert got["settings"] == {k: v for k, v in values.items() if k not in ("color", "seed")}
    assert brushes.for_stroke(got["settings"])["brush"] == "bristle"
    brushes.rename(tmp_path, b["id"], "Oil 2")
    assert [(x["id"], x["name"]) for x in brushes.saved(tmp_path)] == [(b["id"], "Oil 2")]
    brushes.remove(tmp_path, b["id"])
    assert brushes.saved(tmp_path) == [] and not list((tmp_path / "media" / "brush").iterdir())


def test_unknown_setting_is_loud(tmp_path):
    with pytest.raises(RostrumError, match="no brush settings"):
        brushes.save(tmp_path, "x", {"sizee": 3})


def test_identity_old_files_and_library_across_projects(tmp_path):
    from PIL import Image
    from rostrum_core import project
    from rostrum_paint import library as pics
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(), b.mkdir()
    old = tmp_path / "old.json"
    old.write_text(json.dumps({"brush": "round", "size": 9.0}), encoding="utf-8")
    h56 = project.add_file(a, "brush", "Old one", old)
    Image.new("L", (32, 32), 40).save(tmp_path / "tip.png")
    tip = pics.load(a, tmp_path / "tip.png", "tip", "My tip")["id"]
    one = brushes.save(a, "Mine", {"brush": "round", "texture": tip})
    two = brushes.duplicate(a, one["id"])
    assert one["id"] != two["id"] and two["name"] == "Mine copy" and set(two["where"]) == {"project", "library"}
    assert brushes.get(a, h56["id"])["settings"] == {"brush": "round", "size": 9.0}
    assert len([x for x in brushes.saved(a) if x["name"] == "Mine"]) == 1          # in both places, listed once
    assert [x["where"] for x in brushes.saved(b) if x["name"] == "Mine"] == [["library"]]
    brushes.use(b, one["id"])
    assert any(it["id"] == tip for it in project.items(b, "brushtip"))
    brushes.remove(a, one["id"]), brushes.remove(a, two["id"])
