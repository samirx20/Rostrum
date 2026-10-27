"""The frame-edge check: a subject mostly in the picture but crossing an edge is named (look_frame's reply, look_empty's stretches);
backgrounds that span the picture, things fully in and things fully out are not."""
from rostrum2d.mcp import edge_cut

COMP = {"width": 1000, "height": 500, "fps": 30, "duration": 4, "layers": []}


def test_cut_edges_names_the_edge_and_skips_bleeds_and_whole_things():
    assert edge_cut.cut_edges((400, 100, 600, 700), 1000, 500) == {"bottom": 33}           # a body cut at the bottom
    assert edge_cut.cut_edges((-50, 100, 250, 300), 1000, 500) == {"left": 17}
    assert edge_cut.cut_edges((-100, 100, 1100, 300), 1000, 500) == {}                      # spans the picture sideways: a bleed on purpose
    assert edge_cut.cut_edges((100, 100, 300, 300), 1000, 500) == {}                        # fully in
    assert edge_cut.cut_edges((1100, 100, 1300, 300), 1000, 500) == {}                      # fully out
    assert edge_cut.cut_edges((-180, 100, 20, 300), 1000, 500) == {}                        # mostly out: entering, not cut
    assert edge_cut.cut_edges((-10, 100, 190, 300), 1000, 500) == {}                        # a 5 % bleed is under the line
    tight = edge_cut.cut_edges((300, -400, 700, 1500), 1000, 500, character=True)          # a face filling the frame: the body is cut top and bottom
    assert set(tight) == {"top", "bottom"} and edge_cut.cut_edges((300, -400, 700, 1500), 1000, 500) == {}


def test_stretches_are_joined_and_worded():
    comp = {**COMP, "layers": [{"id": "hero", "type": "shape", "shape": "rect", "x": 500, "y": 400, "w": 200, "h": 300}]}
    times = [0.0, 0.5, 1.0]
    rows = edge_cut.scan(comp, times, [{}, {}, {}], 0.5)
    assert [(r["id"], r["edge"], r["start"], r["end"]) for r in rows] == [("hero", "bottom", 0.0, 1.5)] and rows[0]["cut_pct"] == 17
    assert "hero (shape) cut at the bottom edge" in edge_cut.tell(rows) and "0–1.5 s" in edge_cut.tell(rows)
