"""The Move tool's hover outline (Stage.qml, backend.hoverAt) rings exactly what a press there would pick, with and
without Ctrl, before and after going inside a group: an outline that pointed at one layer while the click took
another would be worse than none (critic round 10's matte over its text)."""
from test_screen import bridge  # noqa: F401  (the shared fixture: a small document, the engine stood in)


def test_hover_target_is_the_click_target(bridge):  # noqa: F811
    spots = [(x, y) for x in range(-10, 330, 15) for y in range(-10, 190, 15)]
    seen = set()
    for picked in ("", "ra"):                   # nothing picked; then a piece inside the group (clicks stay among its siblings)
        if picked:
            bridge.select(picked)
        for x, y in spots:
            for deep in (False, True):
                got = bridge.hoverAt(x, y, deep)
                assert got.get("id", "") == bridge.multi.target(x, y, "deep" if deep else "click"), (picked, x, y, deep)
                if got:
                    seen.add(got["id"])
                    assert got["picked"] == bridge.multi.has(got["id"]) and got["w"] > 0
    assert seen                                 # something was hovered (the stand-in engine paints only some layers)
