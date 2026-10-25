"""One way to show each kind of value (ValueKinds.js, run through rostrum_gui.value_kinds): what a field shows,
typed back, gives the same value, and the stored value is never the shown number. Agents and screens rely on it."""
import pytest

from rostrum_gui import value_kinds as K


@pytest.mark.parametrize("kind, value, text", [
    ("percent", 0.8, "80 %"), ("percent", 1.0, "100 %"), ("percent", 0.0, "0 %"),
    ("db", 1.0, "0.0 dB"), ("db", 0.8, "−1.9 dB"), ("db", 0.0, "−∞ dB"), ("db", 2.0, "+6.0 dB"),
    ("pan", -0.3, "L 30"), ("pan", 0.0, "C"), ("pan", 0.3, "R 30"),
])
def test_shown_and_typed_back(kind, value, text):
    assert K.format(kind, value) == text
    assert K.format(kind, K.parse(kind, text)) == text                       # typing what it shows changes nothing
    assert K.parse(kind, text) == pytest.approx(value, abs=0.006)


def test_typed_forms():
    assert K.parse("percent", "80") == pytest.approx(0.8)
    assert K.parse("db", "-6") == pytest.approx(0.501, abs=1e-3)
    assert K.parse("db", "-inf") == 0
    assert K.parse("pan", "R30") == pytest.approx(0.3) and K.parse("pan", "-30") == pytest.approx(-0.3)
    assert K.parse("percent", "lots") is None                                # not a value: the field keeps its own


def test_read_what_was_typed():
    r = K.read
    assert r("", "3*4")["value"] == 12 and r("", "1,5")["value"] == 1.5 and r("", "-45")["value"] == -45
    assert r("", "+20", 100)["value"] == 120 and r("", "+20", 100)["by"] == 20
    assert r("", "*2", [10, 30])["value"] == [20, 60] and r("", "/2", 100)["value"] == 50
    assert r("", "+-45", 100)["value"] == 55 and r("", "12 px")["value"] == 12
    assert r("percent", "+20", 0.5)["value"] == pytest.approx(0.7)
    assert r("", "=time") == {"expression": "=time"}
    assert r("", "abc")["error"].startswith("Type a number or a sum") and "error" in r("", "3*")
