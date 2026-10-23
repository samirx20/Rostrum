"""key.path_handles: writes one position key's spatial handles on x and y (nothing else) in one undo step, and refuses
loudly where there is no x and y key."""
import pytest
from rostrum_core import Document, RostrumError, Who

from rostrum2d import KIND

SAM = Who.person("sam")


def test_path_handles_change_only_that_key_in_one_step():
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "film", "fps": 30, "duration": 4}},
             {"op": "layer.add", "target": "film", "args": {"type": "shape", "id": "a"}},
             *[{"op": "key.add", "target": "a", "args": {"prop": p, "t": t, "v": v}}
               for p in ("x", "y") for t, v in ((0.0, 0), (1.0, 300), (2.0, 600))]], SAM)
    before = {k["id"]: dict(k) for k in d.item("a")["keys"]}
    seq = d.history.seq
    d.apply({"op": "key.path_handles", "target": "a", "args": {"t": 1.0, "out": [40, -80], "in": None}}, SAM)
    assert len(d.history.since(seq)) == 1
    after = {k["id"]: k for k in d.item("a")["keys"]}
    changed = {i for i in after if after[i] != before[i]}
    assert changed == {"a.x.k1000", "a.y.k1000"}
    assert after["a.x.k1000"]["out"] == 40 and after["a.y.k1000"]["out"] == -80 and "in" not in after["a.x.k1000"]
    with pytest.raises(RostrumError, match="no x and y key"):
        d.apply({"op": "key.path_handles", "target": "a", "args": {"t": 1.5, "out": [1, 1]}}, SAM)
