"""A file saved by an earlier build opens: its format's upgrade steps run before the check, so a rule that grew
stricter since (Loop as words) never turns an old file away; one that can't be mended names the item and field."""
import json

import pytest
from rostrum_core import Document, RostrumError
from rostrum_core.storage import paths

from rostrum2d import KIND, run_source


def old_file(tmp_path, edit):
    """A saved film written back as format 1, with `edit(doc data)` applied: what a first build left on disk."""
    d = Document.new(KIND)
    d.run_script("a.py", run_source('comp("film", duration=2)\ntext("hi", body="Hi")\n', "a.py"))
    d.folder, d.item_id = tmp_path, "film"
    d.save()
    p = paths(tmp_path, "film", KIND.ext)
    file = json.loads(p["doc"].read_text(encoding="utf-8"))
    file["version"] = 1
    edit(file["doc"])
    p["doc"].write_text(json.dumps(file), encoding="utf-8")
    p["history"].unlink()
    return p


def test_an_old_file_opens_and_is_brought_up_to_date(tmp_path):
    old_file(tmp_path, lambda doc: doc["comps"][0]["layers"][1].update(loop=True))
    d = Document.open(tmp_path, "film", KIND)
    assert d.data["comps"][0]["layers"][1]["loop"] == "loop"
    assert "Loop written as words" in d.history.changes[-1].label           # one recorded change, so undo takes it back


def test_a_file_that_cannot_be_read_names_the_item_and_field(tmp_path):
    old_file(tmp_path, lambda doc: doc["comps"][0]["layers"][1].update(opacity="a lot"))
    with pytest.raises(RostrumError, match=r"damaged.*hi.*opacity"):
        Document.open(tmp_path, "film", KIND)
