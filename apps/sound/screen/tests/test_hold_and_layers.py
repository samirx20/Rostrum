"""What would break silently: holding H hears the original and letting go goes back (the kit's adapter drops `release`
without a word, so the wiring is checked here), and the Layers group shows only for a sound with layer mates."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Who  # noqa: E402
from screensound import layers  # noqa: E402
from screensound.actions import LIST  # noqa: E402
from screensound.keys import KEYMAP  # noqa: E402
from test_screen import bridge  # noqa: E402,F401  (the screen's fixture: a small song, a stand-in engine)


def test_hold_h_has_a_release():
    assert KEYMAP.held("H") == ["hear_original"]
    assert next(a for a in LIST.actions if a.id == "before_after").release == "hear_back"


def test_layers_only_with_mates(bridge, tmp_path):  # noqa: F811
    import wave
    wav = tmp_path / "slam.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); w.writeframes(bytes(9600))
    doc = bridge.doc
    track = doc.data["tracks"][0]["id"]
    add = {"op": "clip.add", "target": [track], "args": {"media": str(wav), "at": 1.0, "group": "slam"}}
    doc.apply([add], Who.person("sam"))
    first = doc.data["tracks"][0]["clips"][-1]["id"]
    assert layers.of(doc, [first]) == {}                           # a group of one is not layered
    doc.apply([{**add, "args": {**add["args"], "at": 1.2}}], Who.person("sam"))
    got = layers.of(doc, [first])
    assert got["group"] == "slam" and [r["here"] for r in got["rows"]].count(True) == 1 and len(got["rows"]) == 2
    assert layers.of(doc, []) == {}
