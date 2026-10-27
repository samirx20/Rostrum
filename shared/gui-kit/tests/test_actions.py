"""The four doors of the one action list agree (an action needing two never shows for one, anywhere), and the key
map refuses an app key that takes a shared one."""
from types import SimpleNamespace

import pytest

from rostrum_gui.actions import Action, ActionList, bar, commands, menu
from rostrum_gui.keymap import KeyMap

COMBINE = Action("combine", "Combine", kinds=("shape",), min_targets=2, importance="primary", job="group",
                 calls=lambda f: [{"op": "shape.boolean", "target": list(f.ids), "args": {}}])


def _facts(n):
    return SimpleNamespace(ids=[f"s{i}" for i in range(n)], items=[{"id": f"s{i}", "type": "shape"} for i in range(n)])


def _doors(acts, facts):
    entries = acts.available(facts)
    return ([i["id"] for i in bar(entries, "")["items"]], [m["value"] for m in menu(entries)],
            [c["key"] for c in commands(entries, "")], acts.on_key(facts, "Ctrl+G"))


def test_min_targets_agree_across_doors():
    acts = ActionList([COMBINE], KeyMap("test"))
    on_bar, in_menu, in_box, (entry, why) = _doors(acts, _facts(1))
    assert on_bar == in_menu == in_box == [] and entry is None
    assert why == "Combine needs two or more shapes selected."
    on_bar, in_menu, in_box, (entry, why) = _doors(acts, _facts(2))
    assert on_bar == in_menu == in_box == ["combine"] and entry["id"] == "combine" and entry["keys"] == "Ctrl+G"


def test_app_key_cannot_take_a_shared_key():
    with pytest.raises(ValueError, match="Ctrl\\+G.*shared key.*Group"):
        KeyMap("Rostrum2D", [{"job": "mask", "keys": ["ctrl+g"], "label": "Mask"}])


def test_hold_key_releases_only_what_its_press_ran():
    """Hold H to hear the original: letting go runs the release once; a press that was refused releases nothing."""
    from rostrum_gui.action_hub import ActionHub
    km = KeyMap("RostrumSound", [{"job": "hear_original", "keys": ["H"], "label": "Hear the original", "hold": True}])
    assert km.held("Shift+H") == ["hear_original"] and km.held("G") == []
    ran = []
    hear = Action("hear", "Hear the original", job="hear_original", do="hear_on", release="hear_off")
    hub = ActionHub(ActionList([hear], km), lambda: _facts(n[0]), lambda f: "", None, lambda d, e: ran.append(d),
                    lambda line: ran.append("said"))
    n = [0]                                            # nothing selected: the press is refused
    hub.key("hear_original"), hub.keyUp("hear_original")
    assert ran == ["said"]
    n[0] = 1
    hub.key("hear_original"), hub.keyUp("hear_original"), hub.keyUp("hear_original")
    assert ran == ["said", "hear_on", "hear_off"]
    with pytest.raises(ValueError, match="on its own"):
        KeyMap("x", [{"job": "j", "keys": ["Ctrl+H"], "label": "J", "hold": True}])


def test_the_plus_key_is_one_key():
    """Letting go of "+" (Ctrl + the Plus key) named the key "+" and raised in every app."""
    from rostrum_gui.keymap import normal
    assert normal("+") == "+" and normal("Ctrl++") == "Ctrl++" and normal("ctrl+shift++") == "Ctrl+Shift++"


def test_an_app_keeps_its_short_menu_row_in_the_panel():
    """The settings panel leaves out what right-click has (Group / Ungroup aside); an app's `panel_keeps` keeps its own
    (2D's Order), and Ctrl+K lists it either way."""
    from rostrum_gui.action_views import panel
    from rostrum_gui.actions import SHORT_MENU
    fwd = Action("forward", "Bring forward", kinds=("shape",), importance="primary", job="forward",
                 calls=lambda f: [{"op": "layer.order", "target": list(f.ids), "args": {"by": 1}}])

    def ids(acts):
        return [i["id"] for r in panel(acts.available(_facts(1)), acts.short_menu, acts.panel_keeps)["rows"]
                for i in r["items"]]
    plain = ActionList([fwd], KeyMap("test"), short_menu=SHORT_MENU)
    kept = ActionList([fwd], KeyMap("test"), short_menu=SHORT_MENU, panel_keeps=("forward",))
    assert ids(plain) == [] and ids(kept) == ["forward"]
    assert [c["key"] for c in commands(kept.available(_facts(1)), "")] == ["forward"]
