"""An MP4 re-export draws only the 2-second segments a change touches (export_cache.py): a wrong reuse would be a silent
wrong frame in the film, a missed reuse the whole film drawn again."""
import subprocess

import pytest
from rostrum_core import Document

from rostrum2d import KIND, run_source, settings
from rostrum2d.mcp import export_cache, export_segments, exporting
from rostrum2d.scene import describe

SRC = '''
comp("c", width=64, height=36, duration=6, fps=10, background="#204060")
for i in range(3):
    shape(f"s{i}", w=20, h=20, fill=COLOURS[i], x=12, y=18, start=2 * i, end=2 * i + 2).key("x", {2 * i: 12, 2 * i + 2: 52})
'''


def _scene(colours):
    d = Document.new(KIND)
    d.run_script("t.py", run_source(f"COLOURS = {colours!r}\n" + SRC, "t.py"))
    return describe(d.data)


def test_a_layer_counts_only_for_the_segments_it_shows_in():
    a, b = _scene(["#ff0000", "#00ff00", "#0000ff"]), _scene(["#ff0000", "#ffff00", "#0000ff"])
    cuts = export_segments.plan(a, 0, 6)
    assert cuts == [(0, 20), (20, 40), (40, 60)]
    ka, kb = export_segments.keys(a, cuts, 0, {}), export_segments.keys(b, cuts, 0, {})
    assert [x == y for x, y in zip(ka, kb)] == [True, False, True]
    a["comp"]["props"]["background"] = "#000000"                 # the composition's own settings: every segment
    assert all(x != y for x, y in zip(ka, export_segments.keys(a, cuts, 0, {})))


@pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")
def test_re_export_reuses_what_did_not_change(tmp_path, monkeypatch):
    monkeypatch.setattr(export_cache, "folder", lambda: tmp_path / "cache")
    s = exporting.settings("t", "mp4", 6.0)

    def export(colours, name):
        return exporting.run("t", _scene(colours), "mp4", s, out=tmp_path / name)

    first = export(["#ff0000", "#00ff00", "#0000ff"], "a.mp4")
    assert first["segments"]["drawn"] == 3
    again = export(["#ff0000", "#00ff00", "#0000ff"], "b.mp4")
    assert again["segments"]["drawn"] == 0 and again["segments"]["reused"] == 3
    one = export(["#ff0000", "#ffff00", "#0000ff"], "c.mp4")          # only the middle section changed
    assert (one["segments"]["drawn"], one["segments"]["drawn_s"]) == (1, 2.0)
    for name in ("a.mp4", "b.mp4", "c.mp4"):                         # the joined film holds every frame
        n = subprocess.run([settings.ffmpeg("ffprobe"), "-v", "error", "-count_frames", "-select_streams", "v", "-show_entries",
                            "stream=nb_read_frames", "-of", "csv=p=0", str(tmp_path / name)], capture_output=True, text=True)
        assert n.stdout.strip() == "60", name
