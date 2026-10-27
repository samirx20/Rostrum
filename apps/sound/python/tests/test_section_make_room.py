"""Ctrl+D and Repeat… on a middle section (critic r12 should-fix 11): with make_room the music and sections after it
move later by the copies' length and the copies land right after it, as one undo step; without it a full gap is
still refused, saying what is there."""
import pytest
from rostrum_core import Document, RostrumError, Who

from rostrum_sound import KIND

P = Who.person()


def _op(op, target, **args):
    return {"op": op, "target": target, "args": args}


def _song():
    """120 bpm (a beat = 0.5 s): intro 0–4, verse 4–8, end 8–12 (beats), a hit on each beat 0, 2, 4, 6, 8, 10."""
    d = Document.new(KIND)
    d.apply([_op("doc.set", ["root"], tempo=120), _op("track.add", [], id="k", instrument="kit", kit="drums"),
             *[_op("hit.add", ["k"], id=f"h{b}", drum="snare", at={"beat": b}) for b in (0, 2, 4, 6, 8, 10)],
             *[_op("section.add", [], name=n, at=a / 2, end=b / 2) for n, a, b in (("intro", 0, 4), ("verse", 4, 8), ("end", 8, 12))]], P)
    return d


def _hits(d):
    return sorted(round(h["at"]["beat"], 3) for h in d.item("k")["hits"])


def _secs(d):
    from rostrum_sound.doc.select_time import start_of
    return [(s["name"], round(start_of(d.data, s) * 2, 3), round(start_of(d.data, {**s, "at": s["end"]}) * 2, 3)) for s in d.data["sections"]]


def test_a_middle_section_is_refused_without_room():
    with pytest.raises(RostrumError, match="already have"):
        _song().apply(_op("section.duplicate", ["section.verse"]), P)


def test_ctrl_d_makes_room_after_a_middle_section_and_undo_is_exact():
    d = _song()
    before = (_hits(d), _secs(d))
    d.apply(_op("section.duplicate", ["section.verse"], make_room=True), P)
    assert _hits(d) == [0, 2, 4, 6, 8, 10, 12, 14]
    assert _secs(d) == [("intro", 0, 4), ("verse", 4, 8), ("verse-2", 8, 12), ("end", 12, 16)]
    d.undo(P)
    assert (_hits(d), _secs(d)) == before


def test_repeat_on_a_section_makes_that_many_copies():
    d = _song()
    d.apply(_op("section.duplicate", ["section.verse"], make_room=True, times=3), P)
    assert _secs(d) == [("intro", 0, 4), ("verse", 4, 8), ("verse-2", 8, 12), ("verse-3", 12, 16), ("verse-4", 16, 20), ("end", 20, 24)]
    assert _hits(d) == [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]
