"""Scripted drawings: a stroke past the canvas grows the drawing as a painted one does (never a silent clip), and a
re-run with nothing changed changes nothing and stays quick, however many drawings the script made."""
import time

from rostrum_core import Document, Who

from rostrum2d import KIND, run_source

SRC = '''
comp("c", width=640, height=360, fps=24, duration=4)
d = drawing("walk", w=200, h=100, x=320, y=180, eachFrame=True, loop="loop")
for i in range(80):
    p = d.frame(i * 2).paint()
    for j in range(12):
        p.stroke([(10 + j * 15, 20 + i % 7), (40 + j * 15, 60)], color="#336699", size=12)
d.frame(400).paint().stroke([(150, 50), (260, 50)], color="#ff0000", size=10)       # past the right edge
'''


def test_a_scripted_stroke_past_the_edge_grows_the_drawing():
    tree = run_source(SRC, "walk.py")
    walk = tree["comps"][0]["layers"][1]
    assert walk["w"] == 200 + 256 and walk["h"] == 100              # grown right by one step, as paint.stroke grows it
    assert walk["anchorX"] == 0.5 * 200 / 456                         # the same canvas px stays at x, y: nothing moved


def test_rerunning_unchanged_drawings_changes_nothing_and_is_quick():
    d = Document.new(KIND)
    d.run_script("walk.py", run_source(SRC, "walk.py"), Who.script("walk.py"))
    t = time.perf_counter()
    report = d.run_script("walk.py", run_source(SRC, "walk.py", d), Who.script("walk.py"))
    assert report.change is None and not report.held
    assert time.perf_counter() - t < 3.0, "a re-run of 960 unchanged strokes took too long"
