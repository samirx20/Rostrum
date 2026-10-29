"""A field that doesn't apply (seenByCamera on a strip light) never fails a whole script: it is not stored, the reply names
it, and every other edit of the run is applied (a bench run lost ~30 edits to one such field)."""
from rostrum_core import Document

from rostrum3d import KIND, run_source

SRC = '''
mesh("box1", shape="sphere", radius=0.2, width=3)
light("strip", kind="strip", seenByCamera=False, intensity=3)
light("k2", kind="rect", width=0.5, intensity=4)
b = mesh("b2", shape="box")
b.key("y", {0: {"v": 0, "ease": "linear", "stiffness": 200}, 1: 1})
'''


def test_a_field_that_does_not_apply_is_said_and_the_rest_of_the_script_is_applied():
    d = Document.new(KIND)
    tree = run_source(SRC, "s.py", d)
    d.run_script("s.py", tree)
    assert d.item("strip")["seenByCamera"] is True and d.item("strip")["intensity"] == 3
    assert d.item("k2")["width"] == 0.5 and d.item("box1")["width"] == 1.0 and len(d.item("b2")["keys"]) == 2
    said = " ".join(tree.notes)
    assert "strip.seenByCamera: not used on a strip light" in said and "box1.width: not used" in said
    assert "stiffness: not used" in said and "everything else was applied" in said
