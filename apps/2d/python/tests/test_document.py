"""The 2D rules people and agents rely on that would break silently: a script re-run keeps a person's key
edits; an animated field has one source of truth (its keys)."""
import pytest
from rostrum_core import Document, RostrumError, Who

from rostrum2d import KIND, run_source
from rostrum2d.evaluate import value_at

SRC = '''
comp("intro", duration=3)
t = text("title", body="Hi", size=200)
t.key("opacity", {0.2: 0, 0.9: 1}, ease="snappy")
t.key("y", {0.2: 600, 1.0: 540})
'''
SAM = Who.person("sam")


def doc():
    d = Document.new(KIND)
    d.run_script("intro.py", run_source(SRC, "intro.py"))
    return d


def test_rerun_keeps_a_persons_key_edits():
    d = doc()
    d.apply({"op": "key.set", "target": "title.opacity.k900", "args": {"t": 1.4}}, SAM)       # retime a key
    d.apply({"op": "value.set", "target": "title", "args": {"prop": "y", "at": 1.0, "v": 500}}, SAM)
    d.apply({"op": "value.set", "target": "title", "args": {"prop": "x", "v": 700}}, SAM)     # drag
    new = SRC.replace("size=200", "size=240").replace("0.9: 1}", "0.9: 0.8}").replace("1.0: 540", "1.0: 520")
    report = d.run_script("intro.py", run_source(new, "intro.py"))
    title = d.item("title")
    assert (title["x"], title["size"]) == (700, 240)                  # person's move kept, script's size applied
    assert d.item("title.opacity.k900")["t"] == 1.4                   # person's timing kept ...
    assert d.item("title.opacity.k900")["v"] == 0.8                   # ... script's value on the same key applied
    assert d.item("title.y.k1000")["v"] == 500                        # same field changed by both: person wins
    assert [h["key"] for h in report.held] == ["title.y.k1000.v"]     # ... and the agent is told


def test_an_animated_field_is_decided_by_its_keys_only():
    d = doc()
    d.apply({"op": "value.set", "target": "title", "args": {"prop": "y", "at": 2.0, "v": 300}}, SAM)
    title = d.item("title")
    assert title["y"] == 540.0                                        # still value untouched (default)
    assert value_at(title, "y", 2.5) == 300                           # the new key decides
    with pytest.raises(RostrumError, match="is needed"):              # no "at": refused, never a silent still edit
        d.apply({"op": "value.set", "target": "title", "args": {"prop": "y", "v": 1}}, SAM)
    d.apply({"op": "key.clear", "target": "title", "args": {"prop": "y", "at": 2.5}}, SAM)
    assert d.item("title")["y"] == 300 and value_at(d.item("title"), "y", 0) == 300


def test_a_script_cannot_write_a_key_the_document_would_refuse():
    with pytest.raises(RostrumError, match="opacty"):
        run_source('comp("c")\ntext("t").key("opacty", {0: 1})', "bad.py")
    with pytest.raises(RostrumError, match="out of range"):
        run_source('comp("c")\ntext("t").key("opacity", {0: 3})', "bad.py")
