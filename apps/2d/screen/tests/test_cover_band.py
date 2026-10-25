"""The cover band is worked out on a worker once the person pauses (cover_band.py); whatever edits, undos and redos
come during the wait or while the worker runs, it must end up saying exactly what a walk of the whole piece says now,
never an older state's answer. The frame here rides a path: reshaping the path moves the frame, so it counts too."""
import time

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QTest
from rostrum_gui.edits import field_call
from rostrum2d import background as B, cover
from test_screen import bridge as _bridge, FakeEngine  # noqa: F401  (the engine stood in)

import test_screen

SRC = '''
comp("c", width=320, height=180, fps=10, duration=2)
path("road", d="M 0 0 L 10 0", fill="none", stroke=True)
f = frame(ridePath="road", x=160, y=90)
f.key("rideAlong", {0: 0, 2: 1})
shape("back", w=480, h=300, x=160, y=90)
'''
LONG = "M 0 0 L 400 0"      # the frame rides 400 px instead of 10: it shows past an edge


@pytest.fixture
def bridge(monkeypatch):
    monkeypatch.setattr(test_screen, "SRC", SRC)
    yield from _bridge.__wrapped__(monkeypatch)


def _truth(b):
    comp = b.placed()
    layer = next(l for l in comp["layers"] if l["id"] == "back")
    found, once = cover.report(comp, layer, B.shots(comp), float(comp["fps"]))
    return [{"edge": e["edge"], "words": cover.words(e)} for e in found] if once else []


def _settled(b, band):
    """The band once it says what a walk of the piece says now (a stale answer never gets there: 5 s, then it fails)."""
    end, want = time.monotonic() + 5, _truth(b)
    while time.monotonic() < end:
        QTest.qWait(50)
        QCoreApplication.processEvents()
        if band.edges == want and band._asked is None and not band._pause.isActive():
            return band.edges
    raise AssertionError(f"the cover band says {band.edges}, a walk of the piece says {want}")


def test_the_band_ends_as_a_walk_of_the_piece_says_after_edits_undos_and_redos(bridge):
    b, band = bridge, bridge._cover_band
    b.select("back")

    def path(d):
        b.doc.apply([field_call(b.doc, "road", "d", d)], b.who, "Reshape", join=False)
    assert _settled(b, band) == []
    path(LONG)
    assert _settled(b, band), "a longer ride shows past an edge"
    b.undo()                                          # undone during the wait
    QTest.qWait(100)
    assert _settled(b, band) == []
    b.redo()
    QTest.qWait(band.WAIT_MS + 30)                    # the worker is walking the redone state ...
    b.undo()                                          # ... when it is undone again
    assert _settled(b, band) == []
    b.redo()
    b.setValue("x", 200)                              # an edit of the picked layer right after
    _settled(b, band)
