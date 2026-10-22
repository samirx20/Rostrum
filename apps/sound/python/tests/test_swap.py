"""clip.swap: the spot (start, length, fades, layer group) stays, the level follows the loudness, one undo step."""
import numpy as np
import soundfile as sf
from rostrum_core import Document, Who

from rostrum_sound import KIND

P = Who.person()


def _op(op, target, **args):
    return {"op": op, "target": target, "args": args}


def test_swap_keeps_the_spot_and_matches_the_level(tmp_path):
    old, new, short = tmp_path / "old.wav", tmp_path / "new.wav", tmp_path / "short.wav"
    tone = lambda a, s: a * np.sin(np.linspace(0, 440 * 2 * np.pi * s, int(44100 * s)))   # noqa: E731
    sf.write(str(old), tone(.5, 2), 44100)
    sf.write(str(new), tone(.125, 3), 44100)                         # 12 dB quieter
    sf.write(str(short), tone(.5, .5), 44100)
    d = Document.new(KIND)
    d.apply([_op("track.add", [], id="t"), _op("clip.add", ["t"], id="k", media=str(old), at=1, length=2, volume=.8,
                                               fadeIn=.1, fadeOut=.2, group="g")], P)
    d.apply(_op("clip.swap", ["k"], media=str(new)), P)
    c = d.item("k")
    assert c["media"] == str(new) and c["at"] == 1 and c["length"] == 2 and c["fadeIn"] == .1 and c["group"] == "g"
    assert 3.0 < c["volume"] / .8 < 5.0                              # ~ +12 dB (×4)
    d.apply(_op("clip.swap", ["k"], media=str(short), match=False), P)
    assert d.item("k")["length"] == .5 and d.item("k")["volume"] == c["volume"]   # shorter file plays shorter
    d.apply(_op("clip.swap", ["k"], media=str(new), **{"in": 1}), P)
    assert d.item("k")["in"] == 1 and d.item("k")["length"] == .5     # the spot is now the short one's 0.5 s
    d.undo(P)
    d.undo(P)
    assert d.item("k")["media"] == str(new)
