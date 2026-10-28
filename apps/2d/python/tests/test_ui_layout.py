"""Product screens laid out right by default (ui_layout / ui_pointer): a device that fits the picture, blocks made
without y stacked without overlapping, a tap that lands beside a button's words, and ids that stay put on a re-run."""
import pytest
from rostrum_core import Document, RostrumError

from rostrum2d import KIND, run_source
from rostrum2d import ui_layout as U

SRC = '''
comp("main", width=1920, height=1080, fps=30, duration=4)
scr = device("phone")
with scr:
    status_bar(); nav_bar("Trips", action="New")
    hero = card("hero", title="Lisbon dinner", value="$168.00")
    rows = list_rows([("Porto", "3 people", "$412.50"), ("Taxi", "2 people", "$24.50")])
    split = toggle("split", label="Split evenly")
    pay = button("Request")
    tab_bar(["Home", "Trips", "You"])
    cur = pointer()
    tap(cur, pay, at=1.5)
    tap(cur, hero, at=3)
'''


def run(src=SRC):
    d = Document.new(KIND)
    d.run_script("s.py", run_source(src, "s.py"))
    return d


def test_the_phone_fits_the_picture_with_a_margin():
    phone = run().item("phone")
    top, bottom = phone["y"] - phone["h"] / 2, phone["y"] + phone["h"] / 2
    assert phone["x"] == 960 and 60 < top and bottom < 1020 and 0.8 < phone["h"] / 1080 < 0.86
    assert abs(phone["w"] / phone["h"] - 430 / 900) < 1e-6


def test_blocks_made_without_y_stack_without_overlapping_and_a_full_screen_is_refused():
    d = run()
    tops = [(U.own_box(d.item(i))[1], U.bottom(d.item(i))) for i in ("status", "nav", "hero", "list", "split", "button", "tabs")]
    for (t0, b0), (t1, _) in zip(tops, tops[1:]):
        assert t1 >= b0 - 0.01
    title = d.item("nav_title")
    assert title["y"] + title["size"] * 0.6 <= d.item("nav")["h"]          # the title sits inside its own bar
    with pytest.raises(RostrumError, match="past"):
        run(SRC.replace('pay = button("Request")', 'pay = button("Request")\n    list_rows(["a"] * 8)'))


def test_a_tap_puts_the_pointer_beside_the_label_never_on_it():
    d = run()
    keys = {(k["prop"], k["t"]): k["v"] for k in d.item("cursor")["keys"]}
    s = d.item("cursor")["h"]
    for target, at in (("button", 1.5), ("hero", 3.0)):
        tip = (keys[("x", at)], keys[("y", at)])
        shape = (tip[0] - s * 0.08, tip[1] - s * 0.08, s * 0.7, s * 1.08)
        bx, by, bw, bh = U.box_in(d.data, target, "phone_screen")
        assert bx <= tip[0] <= bx + bw and by <= tip[1] <= by + bh          # on the target ...
        for t in [n for n in ("button_label", "hero_title", "hero_value") if n.startswith(target)]:
            from rostrum2d.ui_pointer import overlap
            assert overlap(shape, U.box_in(d.data, t, "phone_screen")) == 0   # ... beside its words


def test_a_rerun_keeps_the_same_ids():
    d = run()
    before = {i for i in ("phone", "phone_screen", "status", "nav", "hero", "list_r1", "split_knob", "button_label",
                          "tabs", "cursor", "cursor_arrow", "cursor_ripple1") if d.item(i)}
    d.run_script("s.py", run_source(SRC, "s.py", d))
    assert {i for i in before if d.item(i)} == before and len(before) == 12
