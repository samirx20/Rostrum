from rostrum2d import advice
from rostrum2d.script import run_source

LOOP = """comp("c", width=64, height=64, fps=10, duration=1)
d = drawing("d", w=64, h=64{each})
for i in range(3):
    d.frame(i * 2).paint().stroke([(5, 5), (50, 50)], color="#fff", size=4)
"""


def test_random_in_a_script_gives_the_same_numbers_every_run():
    """Guards "a re-run gives the same piece": the script's random is seeded, `random(7)` is its own generator."""
    src = 'comp("c", width=64, height=64, fps=10, duration=1)\nimport random\nshape("a", x=random.randint(1, 60), y=random(7).randint(1, 60))'
    pick = lambda: [(n["x"], n["y"]) for n in run_source(src, "s")["comps"][0]["layers"] if n["id"] == "a"]
    assert pick() == pick()


def test_drawings_of_one_loop_share_a_paint_layer_and_a_set_showing_one_drawing_is_advised():
    tree = run_source(LOOP.format(each=""), "s")
    drawing = tree["comps"][0]["layers"][-1]
    assert {p["layer"] if "layer" in p else p["id"] for f in drawing["frames"] for p in f["paints"]} == {drawing["frames"][0]["paints"][0]["id"]}
    assert "shows only the first" in advice.advise(tree)[0]
    assert not advice.advise(run_source(LOOP.format(each=", eachFrame=True"), "s"))
