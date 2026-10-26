"""Ctrl+A picks the layers at the level you are in: a group's own layers once inside it (it picked the outside layers).
No Qt, no engine."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from screen2d import levels  # noqa: E402


class Doc:
    TREE = {"scene": ["a", "grp", "b"], "grp": ["c", "d"]}      # bottom of the list first, as the document keeps them
    PARENT = {"a": "scene", "grp": "scene", "b": "scene", "c": "grp", "d": "grp"}

    def item(self, i):
        return {"layers": [{"id": c, "type": "shape"} for c in self.TREE.get(i, [])]}

    def parent_of(self, i):
        return (self.PARENT[i], 0)


def test_select_all_stays_at_the_level_of_the_pick():
    doc = Doc()
    assert levels.level_of(doc, [], "scene") == ["b", "grp", "a"]
    assert levels.level_of(doc, ["grp"], "scene") == ["b", "grp", "a"]
    assert levels.level_of(doc, ["c"], "scene") == ["d", "c"]
