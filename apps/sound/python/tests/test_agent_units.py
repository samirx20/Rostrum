"""What agents rely on: a bare time is seconds, the wrong beat key is refused with the right one, volume takes dB."""
import pytest
from rostrum_core import RostrumError
from rostrum_sound.doc import fields as FD


def _p(name, op="track"):
    return next(p for p in FD.params(op) if p.name == name)


def test_volume_db_becomes_gain():
    v = _p("volume")
    assert v.check({"db": -6}, "t") == pytest.approx(0.5012, abs=1e-4)
    assert v.check("0 dB", "t") == 1.0
    assert v.check(0.85, "t") == 0.85                      # a bare number stays gain
    with pytest.raises(RostrumError):
        v.check({"db": 30}, "t")


def test_wrong_beat_key_says_which():
    with pytest.raises(RostrumError) as e:
        _p("at", "hit").check({"beats": 2}, "t")
    assert '"beat"' in str(e.value) and e.value.hint and "SECONDS" in e.value.hint
    with pytest.raises(RostrumError) as e:
        _p("dur", "note").check({"beat": 2}, "t")
    assert '"beats"' in str(e.value)
