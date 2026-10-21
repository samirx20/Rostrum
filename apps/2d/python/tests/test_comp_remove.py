"""comp.remove: never the last composition, one undo brings a removed one back."""
import pytest
from rostrum_core import Document, Who
from rostrum_core.errors import RostrumError

from rostrum2d import KIND

SAM = Who.person("sam")


def test_remove_refuses_the_last_comp_and_undo_restores():
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "film"}}, {"op": "comp.add", "args": {"id": "probe"}}], SAM)
    with pytest.raises(RostrumError):
        d.apply({"op": "comp.remove", "target": ["film", "probe"]}, SAM)
    d.apply({"op": "comp.remove", "target": "probe"}, SAM)
    assert [c["id"] for c in d.data["comps"]] == ["film"]
    with pytest.raises(RostrumError):
        d.apply({"op": "comp.remove", "target": "film"}, SAM)
    d.undo(SAM)
    assert [c["id"] for c in d.data["comps"]] == ["film", "probe"]
