"""paint.wash and the coverage report: a whole-canvas wash leaves no bare paper and keeps the canvas's size, and the report
names a strip a wash left bare (with drawnSoFar part way) by its box."""
from rostrum2d import paint_coverage as C, run_source, write_on

SRC = '''
comp("c", width=320, height=180, fps=10, duration=4)
d = drawing("wash", w=320, h=180)
p = d.frame(0).paint()
{wash}
d.key("drawnSoFar", {{0: 0, 2: 1}}, ease="linear")
'''


def _drawing(wash):
    comp = run_source(SRC.format(wash=wash), "w.py")["comps"][0]
    return comp, next(l for l in comp["layers"] if l["id"] == "wash")


def test_a_whole_canvas_wash_covers_to_every_edge_without_growing_the_canvas():
    comp, d = _drawing('p.wash(color="#203060", to="#6080c0", bands=4, granulation=0.5, edge_darken=0.5)')
    assert (d["w"], d["h"]) == (320, 180)
    rep, _, _ = C.report(d["frames"][0], 320, 180, 1.0, C.comp_window(d, comp, 320, 180, 3.0), (320, 180))
    assert rep["bare"] == 0 and rep["gaps"] == [] and rep["painted"] > 0.99


def test_the_report_names_the_bare_strip_while_the_wash_paints_on():
    comp, d = _drawing('p.wash(box=[0, 0, 320, 130], color="#203060", edge=4)')     # stops 50 px short of the bottom
    t = 3.0
    rep, _, _ = C.report(d["frames"][0], 320, 180, write_on.amount_at(d, t), C.comp_window(d, comp, 320, 180, t), (320, 180))
    big = rep["gaps"][0]
    assert big["shape"].startswith("strip along the bottom edge") and big["box"][0] == 0 and big["box"][2] == 320
    assert 125 <= big["box"][1] <= 140 and big["box"][3] == 180 and "bare paper: a 320×" in big["words"]
    half, _, _ = C.report(d["frames"][0], 320, 180, write_on.amount_at(d, 1.0))     # half drawn: more bare
    assert half["bare"] > rep["bare"] + 0.2


def test_a_wash_dries_like_watercolour_unless_told():
    """Left out, a wash's strokes carry the watercolour drying (paint_wash.WATER); 0 turns one off."""
    from rostrum2d import paint_wash
    _, strokes = paint_wash.plan([0, 0, 200, 100], 400, 300, {"color": "#203060"})
    assert all(s[k] == v for s in strokes for k, v in paint_wash.WATER.items())
    _, strokes = paint_wash.plan([0, 0, 200, 100], 400, 300, {"color": "#203060", "pooling": 0.0})
    assert strokes[0]["pooling"] == 0.0
