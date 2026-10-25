"""An empty scene (only its frame) is refused before any file is made, in plain words: the agent tool and the Export
button both take exporting.snapshot(), so an agent never gets a blank video reported as done."""
import pytest
from rostrum_core import Document, Who
from rostrum_core.errors import RostrumError

from rostrum2d import KIND
from rostrum2d.mcp import exporting

SAM = Who.person("sam")


def test_an_empty_scene_is_refused_and_a_layer_lets_it_export():
    d = Document.new(KIND)
    d.apply({"op": "comp.add", "args": {"id": "film"}}, SAM)          # comes with its frame: not something showing
    with pytest.raises(RostrumError) as e:
        exporting.snapshot(d, "film", "mp4")
    assert e.value.person().startswith("There is nothing to export yet")
    d.apply({"op": "layer.add", "target": "film", "args": {"type": "shape", "id": "card"}}, SAM)
    assert exporting.snapshot(d, "film", "mp4")
