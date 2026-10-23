"""Splitting a shared material changes only the split item; the others keep the original untouched, and one undo
brings the shared material back (SPEC §6.2)."""
from rostrum_core import Document, Who

from rostrum3d import KIND, run_source
from rostrum3d.ops_materials import users_of

SAM = Who.person()
SRC = '''
alu = material("alu", start="Brushed metal", baseColor="#c9ccd1")
mesh("a", shape="box", material=alu)
mesh("b", shape="sphere", material=alu)
mesh("c", shape="torus", material=alu)
'''


def test_split_one_of_three_and_undo():
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SRC, "s.py"))
    before = dict(d.item("alu"))
    assert before["anisotropy"] == 0.7 and before["baseColor"] == "#c9ccd1"      # the start, then the script's field
    d.apply({"op": "material.split", "target": ["b"], "args": {}}, SAM)
    new = d.item("b")["material"]
    assert new != "alu" and users_of(d.data, "alu") == ["a", "c"]
    assert dict(d.item("alu")) == before
    own = {k: v for k, v in d.item(new).items() if k not in ("id", "name")}
    assert own == {k: v for k, v in before.items() if k not in ("id", "name")}
    assert d.item(new)["name"] == "b material"
    d.undo(SAM)
    assert users_of(d.data, "alu") == ["a", "b", "c"]
    assert [m["id"] for m in d.data["materials"]] == ["alu"]
