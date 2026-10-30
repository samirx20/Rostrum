"""A 2D script is plain Python: imports, classes, a seeded random, print back in the reply, exit() keeps what was made."""
from rostrum2d.script import run_source

SRC = """
from dataclasses import dataclass
import random, itertools
comp("main", width=640, height=360, duration=2)
@dataclass
class Dot:
    x: float
    def make(self, i):
        return shape(f"d{i}", x=self.x, y=random.Random(i).randint(0, 100))
for i, d in zip(itertools.count(), [Dot(10), Dot(60)]):
    d.make(i)
print("dots", i + 1)
exit()
shape("never")
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
    tree = run_source(SRC, "film.py")
    assert {"d0", "d1"} <= set(ids(tree)) and "never" not in ids(tree)
    assert "print: dots 2" in tree.notes
    assert any("ended at exit() on line 13" in n for n in tree.notes)
    assert run_source(SRC, "film.py") == tree
