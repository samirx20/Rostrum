"""The script's layout words (script_layout.py, tw.py): containers and the layers made in them become the right group
and child fields, x / y inside a container is refused unless set apart, and a device's screen is a plain column."""
import pytest

from rostrum2d import run_source
from rostrum2d.tw import read

HEAD = 'comp("main", width=1920, height=1080, fps=30, duration=2)\n'


def items(src):
    out = {}

    def walk(n):
        for c in n.get("layers", []):
            out[c["id"]] = c
            walk(c)
    walk(run_source(HEAD + src, "s.py")["comps"][0])
    return out


def test_containers_and_their_layers_become_layout_fields():
    d = items('''
with column("menu", x=100, y=80, padding=24, gap=16, w=520, bg="#111827", radius=20):
    text("title", body="Trips", size=32)
    with row("line", gap=12, align="center", w="fill", tw="px-4 justify-between"):
        shape("dot", w=40, h=40, origin="bottom-center", shrink=0)
        text("name", body="Lisbon", size=18, grow=1, margin=4)
    with grid("kpis", columns="1fr 2fr", w="50%", tw="gap-6 p-2"):
        shape("wide", w="fill", h=10, span=2, shift_y=8)
    with stack("pill", h=48, padding=6):
        shape("pill_bg", w="fill", h="fill")
''')
    m = d["menu"]
    assert (m["layout"], m["padding"], m["gap"], m["sizeW"], m["w"], m["sizeH"], m["align"]) == ("column", 24, 16, "fixed", 520, "fit", "stretch")
    assert (m["anchorX"], m["anchorY"], m["x"], m["y"], m["background"], m["bgColor"], m["bgRadius"]) == (0, 0, 100, 80, True, "#111827", 20)
    line = d["line"]
    assert (line["layout"], line["gap"], line["paddingX"], line["justify"], line["sizeW"], line["padding"]) == ("row", 12, 16, "between", "fill", 0)
    assert (d["dot"]["anchorX"], d["dot"]["anchorY"], d["dot"]["layoutShrink"]) == (0.5, 1, 0)
    assert (d["name"]["layoutGrow"], d["name"]["margin"]) == (1, 4)
    k = d["kpis"]
    assert (k["layout"], k["columnsTemplate"], k["sizeW"], k["pctW"], k["gap"], k["padding"]) == ("grid", "1fr 2fr", "percent", 50, 24, 8)
    assert (d["wide"]["sizeW"], d["wide"]["colSpan"], d["wide"]["shiftY"]) == ("fill", 2, 8)
    assert (d["pill"]["layout"], d["pill"]["sizeH"], d["pill"]["h"], d["pill"]["padding"]) == ("stack", "fixed", 48, 6)


def test_x_y_in_a_container_fail_unless_apart_and_child_words_need_a_container():
    with pytest.raises(Exception, match="apart=True"):
        items('with column("c"):\n    shape("s", x=10, y=20, w=5, h=5)\n')
    d = items('with column("c"):\n    shape("badge", x=10, y=20, w=5, h=5, apart=True)\n')
    assert (d["badge"]["layoutApart"], d["badge"]["x"], d["badge"]["y"]) == (True, 10, 20)
    with pytest.raises(Exception, match="not inside one"):
        items('shape("s", w=5, h=5, grow=1)\n')
    with pytest.raises(Exception, match="x= and y="):
        items('card("hero", title="Hi")\n')


def test_tailwind_words_map_to_the_same_arguments_and_an_unknown_one_is_named():
    assert read("flex flex-col gap-4 p-6 items-center justify-between w-full grow col-span-2 w-[320px] rounded-lg bg-[#fff]") == {
        "layout": "column", "gap": 16, "padding": 24, "align": "center", "justify": "between", "w": 320.0, "grow": 1,
        "span": 2, "radius": 8, "bg": "#fff"}
    assert read("w-1/2 h-fit gap-y-2.5 px-[18px] shrink-0") == {"w": "50.0%", "h": "fit", "row_gap": 10, "padding_x": 18, "shrink": 0}
    with pytest.raises(ValueError, match='"text-xl"'):
        read("flex text-xl")


def test_a_device_screen_is_a_column_with_no_white_box_unless_asked():
    d = items('scr = device("phone")\nwith scr:\n    status_bar()\n    button("Pay")\n')
    s = d["phone_screen"]
    assert (s["layout"], s["padding"], s["gap"], s["align"], s["sizeW"], s["sizeH"], s["clip"], s["background"]) == (
        "column", 0, 0, "stretch", "fixed", "fixed", False, False)
    assert "phone_screen_bg" not in d and "phone_screen_round" not in str(s)
    assert d["button"]["sizeW"] == "fill"
    d = items('device("phone", screen="#ffffff", overflow="hidden")\n')
    s = d["phone_screen"]
    assert (s["background"], s["bgColor"], s["clip"]) == (True, "#ffffff", True)
