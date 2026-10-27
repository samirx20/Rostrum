"""A smear's wet ink holds the layer's paint, so it must replace that paint on screen, not lie on it again (a
see-through layer showed a brighter box until the stroke landed: critic r12), it lies where the canvas is laid, and
under the layers above its layer."""
import numpy as np

from screen2d import wet_layers
from screen2d.wet_ink import WetInk


def test_smear_shows_the_paint_once_over_the_world_under_it():
    under = np.zeros((8, 8, 4), np.float32)
    under[...] = (0.4, 0.4, 0.4, 0.4)                       # white paint at 40 %, premultiplied
    ink = WetInk({"size": 4}, "s", 1.0, None, under, place=(100.0, 50.0, 2.0, 2.0))
    ink.covers = True
    assert not ink.ready                                     # waits for the world under its layer (wet.WetView.layer)
    ink.reveal_with(np.zeros((40, 40, 4), np.uint8), (90, 40))
    assert ink.ready
    got = ink.straight(under, (0, 0, 8, 8), (0, 0))
    assert got[0, 0, 0] == 255 and abs(int(got[0, 0, 3]) - 102) <= 1    # the paint once: the screen lays it on `under`


def _scene():
    def node(i, kids=()):
        return {"id": i, "type": "group" if kids else "drawing", "props": {}, "frames": ["f"], **({"layers": list(kids)} if kids else {})}
    return {"comp": {"id": "c", "type": "comp", "props": {"background": "#102030"},
                     "layers": [node("low"), node("g", [node("back"), node("me"), node("in_above")]), node("top")]}}


def test_the_wet_ink_lies_under_the_layers_above():
    """A live stroke shows in its layer's place: under it the world below the layer (a smear: without the layer's paint),
    over it the layers above alone on a see-through background (a live smear showed over every layer: critic r12)."""
    scene = _scene()
    smear = wet_layers.asks(scene, "me", False, "smear")
    group = smear["under"]["comp"]["layers"][1]
    assert [n["id"] for n in smear["under"]["comp"]["layers"]] == ["low", "g"]
    assert [n["id"] for n in group["layers"]] == ["back", "me"] and group["layers"][1]["frames"] == []
    above = smear["above"]["comp"]
    assert above["props"]["background"] == "#00000000"
    assert [n["id"] for n in above["layers"]] == ["g", "top"] and [n["id"] for n in above["layers"][0]["layers"]] == ["in_above"]
    ink = wet_layers.asks(scene, "me", False, "ink")
    assert ink["under"]["comp"]["layers"][1]["layers"][1]["frames"] == ["f"]        # plain ink lies on the layer's paint
    assert wet_layers.asks(scene, "top", False, "ink") == {}                       # nothing above: the world as shown
    assert set(wet_layers.asks(scene, "top", False, "smear")) == {"under"}
    erase = wet_layers.asks(scene, "me", False, "erase")                           # the eraser: the layers above kept
    assert set(erase) == {"under"} and [n["id"] for n in erase["under"]["comp"]["layers"]] == ["low", "g", "top"]
    assert scene["comp"]["layers"][1]["layers"][1]["frames"] == ["f"]               # the shared scene is left as it was


def test_smear_reveal_follows_the_canvas_place():
    world = np.zeros((40, 40, 3), np.uint8)
    world[10:12, 20:22] = 200                                # world px (110..112, 50..52): canvas px (5, 5) at 2x
    ink = WetInk({"size": 4}, "s", 1.0, None, np.zeros((8, 8, 4), np.float32), place=(100.0, 40.0, 2.0, 2.0))
    ink.reveal_with(world, (90, 40))
    got = ink._revealed(0, 0, 8, 8)
    assert got[5, 5, 0] == 200 and got[4, 5, 0] == 0 and got[5, 4, 0] == 0
