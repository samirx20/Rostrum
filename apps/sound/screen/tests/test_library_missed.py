from screensound import adder


def test_empty_search_on_any_kind_says_something():
    """A Library chip with nothing found and an empty search used to crash (max() of nothing)."""
    for kind, _ in adder.KINDS:
        said = adder.missed("", kind)
        assert said["say"] and said["chip"] == ""
    assert adder.missed("   ", "voice")["say"]
