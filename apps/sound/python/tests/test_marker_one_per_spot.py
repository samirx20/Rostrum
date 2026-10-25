"""One spot holds one marker (sound-pro-workflows SPEC § 3.7): `marker.add` at a time that already has a marker fails
loudly, names the one there and changes nothing, so neither a person's M nor an agent makes a double."""
import pytest
from rostrum_core import Document, RostrumError, Who

from rostrum_sound import KIND

P = Who.person()


def test_a_second_marker_on_the_same_spot_is_refused_and_named():
    d = Document.new(KIND)
    d.apply([{"op": "doc.set", "target": ["root"], "args": {"tempo": 120}},
             {"op": "marker.add", "args": {"name": "drop", "at": 2.0}}], P)
    steps = len(d.history.changes)
    with pytest.raises(RostrumError) as err:
        d.apply({"op": "marker.add", "args": {"name": "Marker 2", "at": {"beat": 4}}}, P)     # beat 4 at 120 = 2 s
    assert "drop" in str(err.value)
    assert len(d.history.changes) == steps and len(d.data["markers"]) == 1
    d.apply({"op": "marker.add", "args": {"name": "Marker 2", "at": 2.5}}, P)                # elsewhere: fine
    assert len(d.data["markers"]) == 2
