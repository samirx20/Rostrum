"""Dragging the anchor ring is the agents' layer.anchor (rostrum2d/ops_anchor.py): one undo step, and the same fields
as the op called with the anchor the drag reached."""
from rostrum_core import Document, Who
from rostrum2d import KIND, run_source
from test_screen import SRC, bridge  # noqa: F401  (the shared fixture: a small document, the engine stood in)

FIELDS = ("x", "y", "anchorX", "anchorY")


def test_anchor_drag_is_the_same_as_the_op(bridge):  # noqa: F811
    bridge.select("box")
    n = len(bridge.doc.history.changes)
    assert bridge.beginAnchor()
    for d in (5, 12, 20):                            # the box is 40 px: 20 px right and down = its corner (1, 1)
        bridge.anchorBy(d, d, True)
    bridge.endDrag()
    assert len(bridge.doc.history.changes) == n + 1
    by_hand = {f: bridge.doc.item("box")[f] for f in FIELDS}
    agent = Document.new(KIND)
    agent.run_script("s.py", run_source(SRC, "s.py"))
    agent.apply([{"op": "layer.anchor", "target": ["box"], "args": {"x": 1.0, "y": 1.0}}], Who.person("sam"))
    assert by_hand == {f: agent.item("box")[f] for f in FIELDS} and by_hand["anchorX"] == 1.0
