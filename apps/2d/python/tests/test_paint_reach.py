"""FRICTION A2R-4: a drawing's canvas holds every pixel its strokes paint (soft edges, scatter, a tip leaning on its
side), never cutting a stroke into a hard edge: after a script's strokes near and past the edge, the canvas border is
empty."""
from rostrum_core import Document

from rostrum2d import KIND, run_source

SRC = '''comp("c")
d = drawing("d", w=400, h=300)
p = d.frame(0).paint()
p.stroke([(-40, 150), (440, 160)], size=300, brush="round", hardness=0, opacity=0.8)
p.stroke([(200, 290), (260, 296)], size=40, jitter=0.6, seed=3)
p.stroke([(380, 20), (390, 40, 1, 60, 1)], size=50, tilt_size=1)
'''


def test_the_canvas_border_is_empty_after_soft_scattered_strokes():
    from rostrum_paint import canvas
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SRC, "s.py"))
    d = doc.item("d")
    a = canvas.rgba8(d["frames"][0], int(d["w"]), int(d["h"]))[..., 3]
    assert a.any()
    assert not (a[0].any() or a[-1].any() or a[:, 0].any() or a[:, -1].any()), "paint reaches the canvas edge: cut"


def test_a_small_drawing_made_without_x_y_paints_where_comp_px_say():
    """FRICTION A2R-2: a drawing smaller than the comp, made with no x / y, has canvas px = comp px: a stroke given at
    (1500, 900) shows there, even after its canvas grew to hold it."""
    from rostrum2d.evaluate import resolve
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source('comp("c")\na = drawing("a", w=1100, h=620)\n'
                                      'a.frame(0).paint().stroke([(1500, 900), (1600, 950)], size=20)\n', "s.py"))
    item = doc.item("a")
    p = resolve(item, 0)
    u = item["frames"][0]["paints"][0]["strokes"][0]["points"][0]
    assert (p["x"] - p["anchorX"] * p["w"] + u[0], p["y"] - p["anchorY"] * p["h"] + u[1]) == (1500, 900)
