"""Product screens (ui_layout / ui_blocks / ui_pointer): a device that fits the picture, blocks placed by the column
they are made in (no stacking of their own), a tap that lands beside a button's words where the layout put it, and
ids that stay put on a re-run. Layouts are solved by the stand-in engine (fake_layout.py)."""
import pytest
from rostrum_core import Document

from fake_layout import FakeEngine
from rostrum2d import KIND, run_source, textsize
from rostrum2d import ui_layout as U

SRC = '''
comp("main", width=1920, height=1080, fps=30, duration=4)
scr = device("phone", screen="#ffffff")
with scr:
    status_bar(); nav_bar("Trips", action="New")
    with column("feed", padding=20, gap=14):
        hero = card("hero", h=180, title="Lisbon dinner", value="$168.00")
        rows = list_rows([("Porto", "3 people", "$412.50"), ("Taxi", "2 people", "$24.50")])
        split = toggle("split", label="Split evenly")
        pay = button("Request", w=300)
    tab_bar(["Home", "Trips", "You"])
    cur = pointer()
    tap(cur, pay, at=1.5, spot="beside")
    tap(cur, hero, at=3, spot="beside")
'''


@pytest.fixture(autouse=True)
def fake_engine():
    with textsize.use(FakeEngine()):
        yield


def run(src=SRC, d=None):
    d = d or Document.new(KIND)
    d.run_script("s.py", run_source(src, "s.py", d))
    return d


def test_the_phone_fits_the_picture_with_a_margin():
    phone = run().item("phone")
    top, bottom = phone["y"] - phone["h"] / 2, phone["y"] + phone["h"] / 2
    assert phone["x"] == 960 and 60 < top and bottom < 1020 and 0.8 < phone["h"] / 1080 < 0.86
    assert abs(phone["w"] / phone["h"] - 430 / 900) < 1e-6


def test_blocks_take_slots_in_their_column_and_the_tab_bar_sits_under_a_spacer():
    d = run()
    for i in ("status", "nav", "hero", "list", "split"):
        assert not d.item(i)["layoutApart"] and d.item(i)["sizeW"] == "fill"
    kids = [c["id"] for c in d.item("phone_screen")["layers"]]
    assert kids[kids.index("tabs") - 1] == "tabs_push" and d.item("tabs_push")["layoutGrow"] == 1
    assert d.item("cursor")["layoutApart"]                    # the pointer is over the screen, taking no room


def test_a_tap_puts_the_pointer_beside_the_label_never_on_it():
    d = run()
    keys = {(k["prop"], k["t"]): k["v"] for k in d.item("cursor")["keys"]}
    s = d.item("cursor")["h"]
    from rostrum2d.ui_pointer import overlap
    with textsize.use(FakeEngine()):
        for target, at in (("button", 1.5), ("hero", 3.0)):
            tip = (keys[("x", at)], keys[("y", at)])
            shape = (tip[0] - s * 0.08, tip[1] - s * 0.08, s * 0.7, s * 1.08)
            bx, by, bw, bh = U.box_in(d.data, target, "phone_screen", at)
            assert bx <= tip[0] <= bx + bw and by <= tip[1] <= by + bh          # on the target ...
            for t in [n for n in ("button_label", "hero_title", "hero_value") if n.startswith(target)]:
                assert overlap(shape, U.box_in(d.data, t, "phone_screen", at)) == 0   # ... beside its words


def test_a_rerun_keeps_the_same_ids():
    d = run()
    before = {i for i in ("phone", "phone_screen", "status", "nav", "hero", "list_r1", "split_knob", "button_label",
                          "tabs", "cursor", "cursor_arrow", "cursor_ripple1") if d.item(i)}
    run(SRC, d)
    assert {i for i in before if d.item(i)} == before and len(before) == 12


def test_blocks_take_their_colours_from_the_screen_they_sit_on():
    src = 'comp("main", width=1920, height=1080, fps=30, duration=2)\nwith device("phone"{screen}):\n    tab_bar(["Home", "You"])\n'
    dark, light = run(src.format(screen="")), run(src.format(screen=', screen="#ffffff"'))
    assert dark.item("tabs")["bgColor"] == U.DARK["paper"] and dark.item("tabs_label1")["color"] == U.DARK["muted"]
    assert light.item("tabs")["bgColor"] == U.LIGHT["paper"]


def test_device_draws_the_asked_kind_never_a_swap():
    """Canary 3E R8: device("laptop", ...) drew a phone (the first argument is the id). The id names the kind when kind is
    left out; a device it can't draw, or an id naming another kind than kind=, is refused."""
    assert U.device_kind("laptop") == "laptop" and U.device_kind("macbook_hero") == "laptop"
    assert U.device_kind("hero") == "phone" and U.device_kind("screen", "browser") == "browser"
    for args in (("tablet",), ("laptop", "phone"), ("x", "tablet")):
        with pytest.raises(ValueError):
            U.device_kind(*args)
    d = run('comp("main", width=1920, height=1080, fps=30, duration=1)\nscr = device("laptop", fit=0.74)\n')
    group = next(l for l in d.data["comps"][0]["layers"] if l["id"] == "laptop")
    assert group["name"] == "Laptop" and any(c["id"] == "laptop_base" for c in group["layers"])


def test_a_card_hanging_off_a_device_screen_is_named_once():
    """Canary 3E R8: a chart card hung off a laptop's screen and the look said nothing. The outermost spilling layer is
    named (the card, not its words); a screen that clips (overflow="hidden") is not."""
    from rostrum2d.mcp import review
    src = ('comp("main", width=1920, height=1080, fps=30, duration=1)\nscr = device("laptop", fit=0.5{})\nwith scr:\n'
           '    with column("box", h=900, bg="#ffffff"):\n        text("label", body="Revenue", size=30)\n')
    for clip, named in (("", ["box"]), (', overflow="hidden"', [])):
        d = run(src.format(clip))
        faults, _ = review.doc_faults(d.data, d.data["comps"][0], None, "t")
        assert [f["id"] for f in faults if f["kind"] == "screen_spill"] == named


def test_a_card_given_too_small_an_h_for_its_words_is_named_with_the_h_that_fits():
    """Gemini Argon r2: card(h=190) whose two-line value ran under the panel below it and the look said nothing. A
    laid-out group with a fixed h its words run out of is a text_spill naming the h that fits; left out, h hugs."""
    from rostrum2d.mcp import review
    src = ('comp("main", width=1920, height=1080, fps=30, duration=2)\ncard("tele", x=200, y=200, w=420{}, size=24, '
           'title="Grasp", detail="Error 0.02 mm", value="TARGET ACQUIRED")\n')
    for h, named in ((", h=90", ["tele"]), ("", [])):
        d = run(src.format(h))
        rows = [f for f in review.doc_faults(d.data, d.data["comps"][0], None, "t")[0] if f["kind"] == "text_spill"]
        assert [f["id"] for f in rows] == named
        if rows:
            assert "h=90 is too small" in rows[0]["text"] and "or leave h out so it fits its text" in rows[0]["text"]
