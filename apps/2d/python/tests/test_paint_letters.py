"""paint.letters (ops_paint_letters.py, lettering.py): words become ordinary strokes in writing order, in one undo step;
and several strokes painted in one change all reach the drawing's picture (drawing.py `_mark`: placing each stroke lays
the page out mid-change, which once kept the picture with only the first new stroke)."""
import pytest
from rostrum_core import Document, Who
from rostrum_paint import ink

from rostrum2d import KIND, drawing as D, lettering

SAM = Who.person("sam")


def doc() -> Document:
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "film", "width": 1280, "height": 720, "duration": 2}},
             {"op": "layer.add", "target": "film", "args": {"type": "drawing", "id": "ink"}}], SAM)
    return d


def strokes(d):
    return [s for f in d.item("ink").get("frames", []) for p in f["paints"] for s in p["strokes"]]


def test_letters_are_strokes_in_writing_order_in_one_undo_step():
    d = doc()
    d.apply({"op": "paint.letters", "target": "ink", "args": {"text": "Hi", "font": "sans", "height": 100, "x": 200,
                                                               "y": 400, "size": 8, "taper_end": 2}}, SAM)
    got = strokes(d)
    assert len(got) == len(lettering.strokes("Hi", font_name="sans", size=100))      # H: 3 strokes, i: 2
    assert all(s["size"] == 8 and s["taper_end"] == 2 for s in got)                  # the brush goes on every stroke
    assert got[0]["points"][0][0] < got[-1]["points"][0][0]                          # left to right, as written
    d.undo(SAM)
    assert strokes(d) == []


def test_a_letter_the_fonts_lack_fails_loudly():
    with pytest.raises(Exception, match="no strokes for"):
        doc().apply({"op": "paint.letters", "target": "ink", "args": {"text": "naïve"}}, SAM)


def test_every_stroke_of_one_change_reaches_the_picture():
    d = doc()
    d.apply({"op": "paint.stroke", "target": "ink", "args": {"points": [[100, 100], [300, 100]], "size": 10}}, SAM)
    d.apply([{"op": "paint.stroke", "target": "ink", "args": {"points": [[100, 200 + 60 * i], [300, 200 + 60 * i]],
                                                                "size": 10}} for i in range(3)], SAM)
    item, (w, h) = d.item("ink"), D.canvas_size(d.item("ink"))
    frame = item["frames"][0]
    whole = ink.png(frame, w, h)[1]                     # the ink of all four strokes, made from the strokes themselves
    assert whole[3] > 200                               # it spans the first line to the last (y 100 .. 320)
    assert D.inked(item, frame)["crop"] == whole        # the picture the engine gets: not only the first new stroke


def test_script_letters_paint_the_same_strokes():
    from rostrum2d import run_source
    d = Document.new(KIND)
    d.run_script("t.py", run_source('comp("film", width=1280, height=720, duration=2)\n'
                                    'p = drawing("ink").frame(0).paint()\n'
                                    'p.letters("Hi", x=200, y=400, height=100, font="sans", size=8)\n', "t.py"))
    got = strokes(d)
    assert len(got) == len(lettering.strokes("Hi", font_name="sans", size=100)) and all(s["size"] == 8 for s in got)
