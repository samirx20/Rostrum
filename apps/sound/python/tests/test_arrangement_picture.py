"""look_arrangement's picture and facts (ears/arrangement.py, ears/draw_arrangement.py): the PNG is written without
rendering, and every track reports its written level (velocity × fader, automation included) and its register."""
from PIL import Image
from rostrum_core import Document

from rostrum_sound import KIND, run_source
from rostrum_sound.ears import arrangement as A
from rostrum_sound.ears.draw_arrangement import arrangement_picture

SCRIPT = """tempo(120); beats_per_bar(4); key("D minor"); length(bar(5))
marker("drop", at=bar(3)); section("verse", bar(1), bar(3)); section("chorus", bar(3), bar(5))
b = track("bass", builtIn="piano", volume=0.5)
b.note("D2", at=bar(1), dur=1.0, vel=1.0); b.note("Bb2", at=bar(3), dur=1.0, vel=1.0)
d = track("drums", kit="drums"); d.hit("kick", at=bar(1), vel=0.5); d.hit("snare", at=bar(3), vel=1.0)
d.automate("volume", [(0, 0.1), (bar(3), 1.0)])
"""


def _arr():
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SCRIPT, "s.py"))
    return A.read(doc.data)


def test_levels_and_register_come_from_velocity_fader_and_automation():
    arr = _arr()
    bass, drums = (next(t for t in arr["tracks"] if t["id"] == i) for i in ("bass", "drums"))
    lb = A.levels(bass, arr["key"])
    assert lb["level_db"] == -6.0 and lb["register"]["low"] == "D2" and lb["register"]["high"] == "Bb2"
    ld = A.levels(drums)
    assert ld["drums"] == ["kick", "snare"] and ld["register"] is None
    assert ld["level_db_range"] == [-26.0, 0.0]          # kick 0.5 × automated 0.1, snare 1.0 × 1.0
    assert drums["automated"] and not bass["automated"]


def test_the_picture_is_written(tmp_path):
    png = arrangement_picture(str(tmp_path / "a.png"), _arr(), title="t")
    with Image.open(png) as im:
        assert im.width == 1600 and im.height > 200
