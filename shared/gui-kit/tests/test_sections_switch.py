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
