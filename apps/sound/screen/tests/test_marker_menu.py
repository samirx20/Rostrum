"""The kit's marker menu built from Sound's OWN marker operations (marker_menu.MarkerOps): the rows a Sound flag's
right-click will show come from Sound's registry and run Sound's calls, and Move to playhead is absent when the marker
is already there. 2D's menu (the project's markers) stays as it was."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_gui import marker_menu as MM  # noqa: E402
from rostrum_gui.actions import Action  # noqa: E402
from rostrum_sound import KIND  # noqa: E402

SOUND = MM.MarkerOps(KIND.registry, rename=("marker.set", "Rename marker"), move="marker.set", colour="marker.set",
                     remove="marker.remove")


def flat(rows):
    """Every row's value, a submenu's (Colour ▸) included."""
    return [v for r in rows for v in [r["value"], *flat(r.get("sub") or [])]]


def test_sounds_markers_make_the_menu_from_sounds_operations():
    own = Action(id="put_sound", label="Put a sound here", kinds=("marker",), calls=lambda f: [{"op": "sound.add", "args": {}}], rank=35,
                 importance="secondary", group="sound")
    menu = MM.MarkerMenu(SOUND, extra=[own])
    facts = MM.MarkerFacts(["marker.drop"], playhead=4.0, at=2.0)
    ids = flat(menu.rows(facts))
    assert ids[0] == "marker.rename" and "marker.move" in ids and "put_sound" in ids and ids[-1] == "marker.remove"
    assert menu.entry(facts, "marker.move")["calls"] == [{"op": "marker.set", "target": ["marker.drop"], "args": {"at": 4.0}}]
    assert menu.entry(facts, "marker.remove")["calls"][0]["op"] == "marker.remove"
    assert menu.entry(facts, "marker.rename")["do"] == "rename"
    colour = KIND.registry.get("marker.set").param("colour") is not None    # Colour ▸ only once Sound's markers have one
    assert any(i.startswith("colour:") for i in ids) == colour
    there = MM.MarkerFacts(["marker.drop"], playhead=2.0, at=2.0)
    assert "marker.move" not in flat(menu.rows(there))


def test_the_projects_menu_is_unchanged():
    ids = flat(MM.rows(MM.MarkerFacts(["m1"], playhead=1.0, at=0.0)))
    assert ids.count("marker.rename") == ids.count("marker.move") == ids.count("marker.remove") == 1
    assert sum(1 for i in ids if i and i.startswith("colour:")) == len(MM.COLOURS)
