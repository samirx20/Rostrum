from screensound import adder


def test_empty_search_on_any_kind_says_something():
    """A Library chip with nothing found and an empty search used to crash (max() of nothing)."""
    for kind, _ in adder.KINDS:
        said = adder.missed("", kind)
        assert said["say"] and said["chip"] == ""
    assert adder.missed("   ", "voice")["say"]


def test_orchestra_words_find_the_orchestra():
    """"orchestra" / "orchestral" / "cinematic" find the orchestral sections and solos (critic r12 found nothing)."""
    for q in ("orchestra", "orchestral", "cinematic"):
        got = {e["key"] for e in adder.find(q, "")}
        assert {"builtIn:strings", "builtIn:brass", "builtIn:harp", "builtIn:timpani", "builtIn:clarinet"} <= got, q
    assert "Try:" in adder.missed("qqqqq", "")["say"]
