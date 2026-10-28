"""The film as one script: a field keyed from a Python function or list (item.sample), scramble(), and the loud,
named refusals when a second script reaches for the first one's scene or layers (script_others)."""
import pytest
from rostrum_core import Document, RostrumError

from rostrum2d import KIND, run_source

HEAD = 'comp("main", width=640, height=360, fps=10, duration=2)\n'


def _keys(root, id_, prop):
    from rostrum_core.tree import walk
    node = next(i for i in walk(root, KIND.lists) if i.get("id") == id_)
    return sorted((k["t"], k["v"]) for k in node["keys"] if k["prop"] == prop)


def test_sample_keys_a_function_and_a_list_one_key_per_frame():
    root = run_source(HEAD + 'd = shape("d", w=10, h=10)\nd.sample("x", lambda t: 100 + t * 10, start=1, end=1.5)\n'
                      'shape("e", w=10, h=10).sample("y", [5, 6, 7], start=0.2, every=2)\n', "s.py")
    assert _keys(root, "d", "x") == [(1.0, 110), (1.1, 111), (1.2, 112), (1.3, 113), (1.4, 114), (1.5, 115)]
    assert _keys(root, "e", "y") == [(0.2, 5), (0.4, 6), (0.6, 7)]


def test_sample_names_the_time_its_function_failed():
    with pytest.raises(RostrumError, match=r"line 2.*t=1.0 s: ZeroDivisionError"):
        run_source(HEAD + 'shape("d").sample("x", lambda t: 1 / (t - 1), start=0.5, end=1.5)\n', "s.py")


def test_scramble_steps_into_the_final_words():
    root = run_source(HEAD + 'scramble("s", "AB 12", start=0, end=1, rate=4, size=40, x=320, y=180)\n', "s.py")
    from rostrum_core.tree import walk
    g = next(i for i in walk(root, KIND.lists) if i.get("id") == "s")
    bodies = [k["body"] for k in g["layers"]]
    assert g["swap"] and bodies[-1] == "AB 12" and len(bodies) == 5
    assert all(b[2] == " " and b[0].isupper() and b[3].isdigit() for b in bodies)     # each character keeps its kind
    assert [v for _, v in _keys(root, "s", "show")] == [0, 1, 2, 3, 4]


def test_a_second_script_is_told_who_made_the_scene_and_the_layer():
    d = Document.new(KIND)
    d.run_script("film.py", run_source(HEAD + 'shape("dot0", w=10, h=10)\n', "film.py", d))
    with pytest.raises(RostrumError, match=r'scene "main" was made by script "film.py"'):
        run_source(HEAD + 'shape("b")\n', "extras.py", d)
    with pytest.raises(RostrumError, match=r'"dot0" is in the document, made by script "film.py"'):
        run_source('comp("other", duration=2)\nlayer("dot0").set(w=12)\n', "extras.py", d)
    run_source(HEAD + 'shape("dot0", w=12, h=10)\n', "film.py", d)       # the script that made it re-runs freely
