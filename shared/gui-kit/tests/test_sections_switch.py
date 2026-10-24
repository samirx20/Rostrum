"""A folded group a toggle switches on is added in one click and removed with its heading's −; the toggle is never its
own row there (sections.switch_of; Sam, 2026-10-24: "+ Outline" then an on/off row asked twice)."""
from rostrum_core import Param

from rostrum_gui import rows, sections

ON = {"is": ["stroke", True]}
OP = type("Op", (), {"params": [
    Param.number("w", label="Width", group="Shape", importance="primary", default=1.0),
    Param.toggle("stroke", label="Outline", group="Outline", importance="secondary", default=False),
    Param.color("strokeColor", label="Outline colour", group="Outline", importance="secondary", valid_when=ON, default="#fff"),
    Param.number("strokeWidth", label="Outline width", group="Outline", importance="secondary", valid_when=ON, default=2.0),
]})()


def _shown(item, opened=()):
    out = rows.evaluate(sections.layout(OP, "shape"), item, {}, False, opened=opened)
    names = next(r for r in out if r["row"] == "folds")["names"]
    return [r["id"] for r in out if r["valid"]], [(n["group"], n["switch"]) for n in names]


def test_a_switched_group_is_a_name_until_on_then_open_without_its_switch_row():
    assert sections.switch_of(OP.params[1:]) == "stroke"
    shown, names = _shown({"stroke": False})
    assert "stroke" not in shown and ("Outline", "stroke") in names
    shown, names = _shown({"stroke": True}, opened={"Outline": False})       # on = open, whatever was folded by hand
    assert {"fold:Outline", "strokeColor", "strokeWidth"} <= set(shown) and "stroke" not in shown and not names


BLUR = type("Op", (), {"params": [
    Param.number("w", label="Width", group="Frame", importance="primary", default=1.0),
    Param.number("shutter", label="Amount", group="Motion blur", importance="secondary", default=0.0, words={0.0: "Off"}, on=180.0),
    Param.number("samples", label="Steps", group="Motion blur", importance="deep", default=8,
                 valid_when={"not": {"is": ["shutter", 0]}}),
    Param.text("raw", label="Raw", group="Frame", importance="secondary", default="", shown="script"),
    Param.number("sx", label="Stretch", group="Frame", importance="secondary", default=1.0, shown="changed"),
]})()


def test_a_number_whose_default_is_off_is_its_groups_switch_and_stays_as_the_amount():
    static = sections.layout(BLUR, "scene")
    fold = next(r for r in static if r.get("fold") == "Motion blur")
    assert (fold["switch"], fold["on"], fold["off"]) == ("shutter", 180.0, 0.0)
    out = rows.evaluate(static, {"shutter": 0.0}, {}, False)
    assert [n["group"] for n in next(r for r in out if r["row"] == "folds")["names"]] == ["Motion blur"]
    on = {r["id"] for r in rows.evaluate(static, {"shutter": 180.0}, {}, False) if r["valid"]}
    assert {"fold:Motion blur", "shutter"} <= on          # open while on, the amount still a row


def test_script_params_never_show_and_changed_ones_only_when_changed():
    static = sections.layout(BLUR, "scene")
    shown = lambda item: {r["id"] for r in rows.evaluate(static, item, {}, False) if r["valid"]}  # noqa: E731
    assert "raw" not in shown({"raw": "M 0 0"}) and "sx" not in shown({"sx": 1.0}) and "sx" in shown({"sx": 1.5})
