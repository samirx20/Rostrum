"""A 2D script acts as written (TOOLBUGS 2d-rebench B2-B5): marker times work in the script's own reads (a group's fit,
counter's at=), a field given where it does nothing is said in the reply (shiftY outside a layout), a glow's colour turns
Layer's own colour off, and a counter in a column is laid out as a fixed leaf of its widest number."""
import pytest
from rostrum_core import Document, RostrumError, markers as M
from rostrum_core.who import Who

from fake_layout import FakeEngine
from rostrum2d import KIND, run_source, textsize

HEAD = 'comp("main", width=1920, height=1080, fps=30, duration=8)\n'


class CountingEngine(FakeEngine):
    """A counter measures as its number now (10 px a character, prefix included), so the widest number shows."""

    def measure(self, items):
        return {i["id"]: (10.0 * len(f'{i["countPrefix"]}{i["count"]:.0f}') if i.get("counter") else 10.0 * len(i["body"]),
                          i["size"]) for i in items}


@pytest.fixture
def engine():
    e = CountingEngine()
    with textsize.use(e):
        yield e


def _run(body, folder=None):
    d = Document.new(KIND)
    d.folder = folder
    tree = run_source(HEAD + body, "s.py", d)
    return tree, {n["id"]: n for c in tree["comps"] for n in _all(c)}


def _all(node):
    for c in node.get("layers", []):
        yield c
        yield from _all(c)


def test_marker_keys_inside_a_group_on_that_marker_and_a_counter_on_a_marker(tmp_path, engine):
    M.edit(tmp_path, [{"op": "marker.add", "args": {"name": "open", "at": 1.0}}], Who.person("sam"))
    _, items = _run('marker("s2", 4)\n'
                    'with group("g", start="#s2"):\n'
                    '    h = text("h1", body="Hello")\n'
                    '    h.key("opacity", {"#s2": 0, "#s2+0.7": 1})\n'
                    'counter("n", 0, 100, at="#open+1.4", duration=1.8)\n', tmp_path)
    assert sorted(k["t"] for k in items["h1"]["keys"]) == ["#s2", "#s2+0.7"]          # kept on the marker
    assert sorted(k["t"] for k in items["n"]["keys"] if k["prop"] == "count") == ["#open+1.4", "#open+3.2"]
    with pytest.raises(RostrumError) as err:
        _run('counter("n", 0, 100, at="#opne+1.4")\n', tmp_path)
    assert "opne" in str(err.value) and "open" in str(err.value).split("opne", 2)[-1]   # names the markers there


def test_a_field_given_where_it_does_nothing_is_said_and_a_glow_colour_is_used(engine):
    tree, items = _run('phone = shape("phone", w=100, h=100)\n'
                       'phone.key("shiftY", {0: 40, 1: 0})\n'
                       'with column("c", x=0, y=0):\n'
                       '    shape("s2", w=10, h=10, shift_x=5)\n'
                       't = text("t", body="hi")\n'
                       't.effect("glow", "warm", color="#ff8800")\n'
                       't.effect("glow", "kept", color="#ff8800", ownColor=True)\n')
    assert [n for n in tree.notes if "shiftY on phone" in n and "key y" in n]
    assert not [n for n in tree.notes if "s2" in n]                                   # in a column it moves it
    assert not [n for n in tree.notes if "intro" in n]                                # a section's w / h is its box
    glows = {e["id"]: e for e in items["t"]["effects"]}
    assert glows["warm"]["ownColor"] is False and glows["warm"]["color"] == "#ff8800"
    assert glows["kept"]["ownColor"] is True and [n for n in tree.notes if n.startswith("color on kept")]


def test_a_counter_in_a_column_is_a_leaf_of_its_widest_number(engine):
    from rostrum2d.layout import Plan
    tree, _ = _run('with column("c", x=200, y=200, gap=10):\n'
                   '    text("a", body="Total")\n'
                   '    counter("n", 0, 12500, at=1, duration=2, prefix="$")\n')
    leaf = next(c for c in Plan(tree["comps"][0], 0.0).trees[0]["children"] if c["id"] == "n")
    assert leaf["kind"] == "leaf" and leaf["w"] == 10.0 * len("$12500")              # not "$0": the column stays still
