"""A kept fault must quote the brief that asks for it (3E r8 canary: Haiku kept a dull top with an invented reason)."""
import pytest
from rostrum_core import Document
from rostrum_core.errors import RostrumError
from rostrum_core.mcp import faults as shared_faults

from rostrum_sound import KIND, brief, run_source
from rostrum_sound.mcp import brief_keep


def _dull():
    return [{"id": "dull_top", "what": "the top end is dull", "when": None, "fix": "brighten the piano"}]


def test_invented_reason_is_refused_and_the_reply_says_why():
    data = {"brief": "A 4-bar piano chord progression at 90 bpm"}
    found = _dull()
    keep = brief_keep.screen(found, {"dull_top": "a soft warm piano progression is meant to be dark"}, data)
    assert keep == {}
    with pytest.raises(RostrumError) as e:
        shared_faults.deliver(found, keep, "render_mix")
    assert "keep refused" in str(e.value) and "fix it instead: brighten the piano" in str(e.value)
    # quoting the brief does not help when the quoted words never ask for a dark sound
    found = _dull()
    assert brief_keep.screen(found, {"dull_top": 'the brief says "a 4-bar piano chord progression"'}, data) == {}
    assert "dark or muffled" in found[0]["fix"] and "dull_top" in found[0]["fix"]


def test_reason_quoting_a_brief_that_asks_for_it_is_kept():
    data = {"brief": "A dark, muffled piano loop for a night scene, 90 bpm"}
    keep = {"dull_top": 'the brief asks for "dark, muffled"'}
    assert brief_keep.screen(_dull(), keep, data) == keep
    said = {"dull_top": "it is a dark muffled piano loop"}
    assert brief_keep.screen(_dull(), said, data) == said
    assert brief.asks(data, "dull_top") == "A dark"
    assert brief.asks(data, "clean_ending") is None


def test_no_brief_refuses_every_keep():
    found = [{"id": "loudness", "what": "-17 LUFS", "when": None, "fix": "edit_loudness"}]
    assert brief_keep.screen(found, {"loudness": "a quiet piece"}, {}) == {}
    assert found[0]["fix"].startswith("keep refused: no brief stored") and 'brief("...")' in found[0]["fix"]


def test_script_brief_is_on_the_song():
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source('brief("Lo-fi, underwater keys")\ntrack("p", builtIn="piano").note("C4", 0, 1)', "s.py"))
    assert brief.text(doc.data) == "Lo-fi, underwater keys" and brief.asks(doc.data, "dull_top") == "Lo-fi"


def test_a_delivery_fade_is_kept_only_when_the_brief_asks_for_a_fade():
    from rostrum_sound.mcp.brief_keep import why_not
    decay = {"brief": "Then it settles and decays to a quiet ending at 50 s."}
    assert why_not("bad_ending", 'the brief says "settles and decays to a quiet ending"', decay) is not None
    fade = {"brief": "A 20 s bed that should fade out at the end."}
    assert why_not("bad_ending", 'the brief asks it to "fade out at the end"', fade) is None
