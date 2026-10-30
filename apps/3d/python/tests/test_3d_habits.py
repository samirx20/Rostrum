"""Agents' common habits are read, not refused, and the reply says what was read: aim= given as what to aim at."""
from rostrum_core import Document

from rostrum3d import KIND, run_source

SRC = '''
bottle = mesh("bottle", shape="cylinder")
light("key", kind="rect", aim="bottle", intensity=3)
light("fill", kind="rect", aim=bottle, roll=90, intensity=2)
camera("cam", z=4, aim=(0, 1, 0))
camera("cam2", z=3, aim="none")
'''


def test_aim_given_as_an_id_an_item_or_a_point_works_like_aim():
    d = Document.new(KIND)
    tree = run_source(SRC, "s.py", d)
    d.run_script("s.py", tree)
    assert (d.item("key")["aim"], d.item("key")["aimItem"]) == ("item", "bottle")
    assert (d.item("fill")["aim"], d.item("fill")["aimItem"], d.item("fill")["roll"]) == ("item", "bottle", 90)
    cam = d.item("cam")
    assert (cam["aim"], cam["aimX"], cam["aimY"], cam["aimZ"]) == ("point", 0.0, 1.0, 0.0)
    assert d.item("cam2")["aim"] == "none"
    assert 'key: aim="bottle" was read as .aim(bottle): it points at bottle every frame' in tree.notes
    assert "cam: aim=(0, 1, 0) was read as .aim((0, 1, 0)): it points at that spot every frame" in tree.notes
    assert not any(n.startswith("cam2:") for n in tree.notes)
