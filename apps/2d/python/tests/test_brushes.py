"""My brushes (rostrum2d/brushes.py): a saved brush gives back exactly the settings it was saved with (colour and
seed left out), rename keeps them, delete takes the file too, and a setting that isn't one is refused loudly."""
import pytest
from rostrum2d import brushes
from rostrum_core.errors import RostrumError
from rostrum_paint.fields import brush_defaults


def test_save_round_trips_rename_and_delete(tmp_path):
    values = {**brush_defaults(), "brush": "bristle", "size": 31.0, "hardness": 0.6, "follow": False, "angle": 30.0}
    b = brushes.save(tmp_path, "My oil", values)
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
