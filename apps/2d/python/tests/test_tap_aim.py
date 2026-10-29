"""tap(): the tip lands on the target's centre, chases a target that moves, and reacts by `then=`."""
import pytest
from rostrum_core import Document

from fake_layout import FakeEngine
from rostrum2d import KIND, run_source, textsize
from rostrum2d import ui_layout as U

HEAD = '''
comp("main", width=1920, height=1080, fps=30, duration=5)
scr = device("phone", screen="#ffffff")
with scr:
    with column("feed", padding=20, gap=14):
        pay = button("Request", w=300)
    cur = pointer()
'''


@pytest.fixture(autouse=True)
def fake_engine():
    with textsize.use(FakeEngine()):
        yield


def run(body):
    d = Document.new(KIND)
    d.run_script("s.py", run_source(HEAD + "".join("    " + ln + "\n" for ln in body.strip().splitlines()), "s.py", d))
    return d


def tracks(d, prop):
    return sorted((k["t"], k["v"]) for k in d.item("cursor")["keys"] if k["prop"] == prop)


def centre(d, t):
    bx, by, bw, bh = U.box_in(d.data, "button", "phone_screen", t)
    return bx + bw / 2, by + bh / 2


def test_the_tip_lands_on_the_centre_with_two_eased_keys_when_the_target_stands_still():
    d = run('tap(cur, pay, at=2)')
    assert tracks(d, "x")[-1] == (2.0, pytest.approx(centre(d, 2)[0])) and len(tracks(d, "x")) == 2
    assert tracks(d, "y")[-1][1] == pytest.approx(centre(d, 2)[1])


def test_a_moving_target_is_chased_and_followed_during_hold():
    d = run('pay.key("shiftY", {0: 0, 3: -200}, ease="linear")\ntap(cur, pay, at=2, hold=0.5)')
    xs, ys = tracks(d, "x"), tracks(d, "y")
    assert len(ys) > 10 and ys[-1][0] == pytest.approx(2.5)
    for t, v in ys:
        if t >= 2:
            assert v == pytest.approx(centre(d, t)[1], abs=1.0)


def test_reactions_pick_what_happens_and_unknown_names_fail_loudly():
    d = run('tap(cur, pay, at=2, then=[("highlight", "#ff0000")])')
    assert any(k["prop"] == "fill" for k in d.item("button_bg")["keys"]) and not d.item("button").get("keys")
    with pytest.raises(Exception):
        d.item("cursor_ripple0")                          # a highlight alone: no press, no ripple
    d = run('tap(cur, pay, at=2, then=["ripple", lambda t: pay.key("rotation", {t: 0, t + 0.2: 10})])')
    assert [k["t"] for k in d.item("button")["keys"] if k["prop"] == "rotation"][0] == 2.0 and d.item("cursor_ripple0")
    with pytest.raises(Exception, match="press, ripple, highlight"):
        run('tap(cur, pay, at=2, then="wiggle")')
