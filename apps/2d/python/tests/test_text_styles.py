"""Named text styles (text_styles.py): a style's change reaches every text following it, in one undo step; a field a
person set by hand on a following text detaches it, so a later style change never overwrites it; styles and links
survive save and open. Silent breakage here means a brand change that misses texts, or one that wipes a person's edit."""
from rostrum_core import Document, Who

from rostrum2d import KIND

SAM = Who.person("sam")


def doc_with_two_titles(folder=None) -> Document:
    d = Document.new(KIND, folder=folder, item="s" if folder else None)
    d.apply([{"op": "comp.add", "args": {"id": "s"}},
             *[{"op": "layer.add", "target": "s", "args": {"type": "text", "id": t}} for t in ("a", "b")],
             {"op": "text.set", "target": "a", "args": {"size": 72, "font": "Roboto Flex", "color": "#ff0000"}}], SAM)
    d.apply([{"op": "style.define", "target": "a", "args": {"name": "Heading", "id": "heading"}}], SAM)
    d.apply([{"op": "style.use", "target": "b", "args": {"style": "heading"}}], SAM)
    return d


def test_a_style_change_reaches_its_texts_and_spares_a_hand_edit():
    d = doc_with_two_titles()
    assert d.item("b")["size"] == 72 and d.item("b")["color"] == "#ff0000"
    d.apply([{"op": "text.set", "target": "b", "args": {"size": 40}}], SAM)           # by hand: b leaves the style
    assert d.item("b")["textStyle"] == ""
    d.apply([{"op": "textstyle.set", "target": "heading", "args": {"size": 90, "color": "#00ff00"}}], SAM)
    assert (d.item("a")["size"], d.item("a")["color"]) == (90, "#00ff00")
    assert d.item("b")["size"] == 40
    d.undo(SAM)                                                                        # one step: style and text together
    assert d.item("heading")["size"] == 72 and d.item("a")["size"] == 72


def test_styles_survive_save_and_open(tmp_path):
    (tmp_path / "docs").mkdir()
    d = doc_with_two_titles(tmp_path)
    d.save()
    again = Document.open(tmp_path, "s", KIND)
    assert again.item("heading")["name"] == "Heading" and again.item("b")["textStyle"] == "heading"
    again.apply([{"op": "textstyle.set", "target": "heading", "args": {"weight": 800}}], SAM)
    assert again.item("b")["weight"] == 800
