"""Recipes (recipe.py): a script's settings changed by a person re-run it. What would break silently: a setting change
that doubles what it made or wipes a person's edit, an undo that leaves half of it, a bad value taken quietly."""
import pytest
from rostrum_core import Document, Who
from rostrum_core.errors import RostrumError

from rostrum3d import KIND, recipe, run_source

SAM = Who.person()
SRC = '''
n = setting("count", 3, min=1, max=20, label="Copies")
tint = setting("tint", "#cc3322", label="Colour")
style = setting("style", "box", choices=["box", "sphere"])
material("paint", baseColor=tint)
for i in range(n):
    mesh(f"post_{i}", shape=style, width=0.1, height=0.5, depth=0.1, radius=0.1, x=i * 0.3, material="paint")
'''


def _doc():
    d = Document.new(KIND)
    d.run_script("fence.py", run_source(SRC, "fence.py", d))
    return d


def _posts(d):
    return sorted(i["id"] for i in d.data["items"] if i["id"].startswith("post_"))


def test_a_script_with_settings_is_a_recipe_and_a_setting_change_reruns_it():
    d = _doc()
    rec = recipe.find(d, "recipe_fence")
    assert rec["values"] == {"count": 3, "tint": "#cc3322", "style": "box"} and _posts(d) == ["post_0", "post_1", "post_2"]
    recipe.rerun(d, "recipe_fence", {"count": 5, "tint": "#2244aa"}, SAM)
    assert _posts(d) == [f"post_{i}" for i in range(5)] and d.item("paint")["baseColor"] == "#2244aa"
    recipe.rerun(d, "recipe_fence", {"count": 2}, SAM)
    assert _posts(d) == ["post_0", "post_1"] and len(d.data["recipes"]) == 1
    assert recipe.made(d, recipe.find(d, "recipe_fence")) == ["post_0", "post_1", "paint"]


def test_a_persons_edit_to_a_made_item_survives_a_setting_change_and_an_agent_rerun():
    d = _doc()
    d.apply({"op": "mesh.set", "target": ["post_1"], "args": {"y": 0.7}}, SAM)
    recipe.rerun(d, "recipe_fence", {"count": 4, "style": "sphere"}, SAM)
    assert d.item("post_1")["y"] == 0.7 and d.item("post_1")["shape"] == "sphere" and len(_posts(d)) == 4
    d.run_script("fence.py", run_source(SRC, "fence.py", d))             # the agent re-runs the same script
    assert len(_posts(d)) == 4 and d.item("post_1")["y"] == 0.7            # the person's Copies stays, so does the move
    d.run_script("fence.py", run_source(SRC.replace('"count", 3', '"count", 6'), "fence.py", d))
    assert len(_posts(d)) == 6                                             # a new default in the script is the script's say


def test_undo_of_a_setting_change_restores_the_values_and_what_it_made():
    d = _doc()
    report, _ = recipe.rerun(d, "recipe_fence", {"count": 6}, SAM)
    assert report.change is not None and len(_posts(d)) == 6
    d.undo(SAM)
    assert len(_posts(d)) == 3 and recipe.find(d, "recipe_fence")["values"]["count"] == 3
    recipe.rerun(d, "recipe_fence", {"count": 4}, SAM)                    # and it still works after the undo
    assert _posts(d) == [f"post_{i}" for i in range(4)]


@pytest.mark.parametrize("values, words", [({"count": 50}, "from 1 to 20"), ({"count": 2.5}, "whole number"),
                                           ({"tint": "red"}, "#rrggbb"), ({"style": "cone"}, "box, sphere"),
                                           ({"cuont": 4}, "count")])
def test_bad_values_are_refused_loudly_and_change_nothing(values, words):
    d = _doc()
    seq = d.seq
    with pytest.raises(RostrumError) as e:
        recipe.rerun(d, "recipe_fence", values, SAM)
    assert words in str(e.value) and d.seq == seq and len(_posts(d)) == 3
