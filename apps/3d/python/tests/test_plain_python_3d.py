"""A 3D script is plain Python: imports, classes, a seeded random, print back in the reply, exit() keeps what was made."""
from rostrum3d.script import run_source

SRC = """
from dataclasses import dataclass
import itertools, random
@dataclass
class Spot:
    x: float
    def place(self, i):
        return mesh(f"b{i}", shape="box", x=self.x + random.Random(i).random())
for i, s in zip(itertools.count(), [Spot(0), Spot(2)]):
    s.place(i)
print("made", i + 1)
exit()
mesh("never", shape="box")
"""


def ids(tree):
    out = []
    def walk(n):
        if isinstance(n, dict):
            if "id" in n:
                out.append(n["id"])
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(dict(tree))
    return out


def test_plain_python_script():
    tree = run_source(SRC, "scene.py")
    assert {"b0", "b1"} <= set(ids(tree)) and "never" not in ids(tree)
    assert "print: made 2" in tree.notes
    assert any("ended at exit() on line 12" in n for n in tree.notes)
    assert run_source(SRC, "scene.py") == tree                   # the seeded random: the same scene every run
