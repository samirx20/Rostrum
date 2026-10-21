"""A PSD text layer becomes a real text item when the app has its font, and is kept as a picture (and reported) when not.
The fixture is psd-tools' own text.psd (MIT); its font is ArialMT, patched in memory to 'Inter-R' for the known-font case."""
from pathlib import Path

from rostrum2d.io.psd import psd_tree

SRC = Path(__file__).parent / "data" / "psd_text.psd"


def _texts(tree):
    return [n for n in tree["layers"] if n["type"] == "text"]


def test_text_is_live_with_a_known_font_and_a_reported_picture_without(tmp_path):
    known = tmp_path / "known.psd"
    known.write_bytes(SRC.read_bytes().replace("ArialMT".encode("utf-16-be"), "Inter-R".encode("utf-16-be")))
    tree = psd_tree(known, fonts={"Inter"})
    (t,) = _texts(tree)
    assert (t["props"]["font"], t["props"]["body"]) == ("Inter", "Line 1\nLine 2\nLine 3 and text")
    unknown = psd_tree(SRC, fonts={"Inter"})
    assert _texts(unknown) == []
    assert any("font 'ArialMT' not installed" in r for r in unknown["report"])
