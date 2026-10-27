"""A smear's wet ink holds the layer's paint, so it must replace that paint on screen, not lie on it again (a
see-through layer showed a brighter box until the stroke landed: critic r12), and it lies where the canvas is laid."""
import numpy as np

from screen2d.wet_ink import WetInk


def test_smear_shows_the_paint_once_over_the_world_without_it():
    under = np.zeros((8, 8, 4), np.float32)
    under[...] = (0.4, 0.4, 0.4, 0.4)                       # white paint at 40 %, premultiplied
    ink = WetInk({"size": 4}, "s", 1.0, None, under, place=(100.0, 50.0, 2.0, 2.0))
    ink.covers = True
    assert not ink.ready                                     # waits for the world without its layer
    world = np.zeros((40, 40, 3), np.uint8)                  # black, world px from (90, 40)
    ink.reveal_with(world, (90, 40))
    assert ink.ready
    got = ink.straight(under, (0, 0, 8, 8), (0, 0))
    assert got[..., 3].min() == 255                          # opaque: what the screen shows there, whole
    assert abs(int(got[0, 0, 0]) - 102) <= 1                 # 40 % white on black, once (twice would be 64 %: 163)


def test_smear_reveal_follows_the_canvas_place():
    world = np.zeros((40, 40, 3), np.uint8)
    world[10:12, 20:22] = 200                                # world px (110..112, 50..52): canvas px (5, 5) at 2x
    ink = WetInk({"size": 4}, "s", 1.0, None, np.zeros((8, 8, 4), np.float32), place=(100.0, 40.0, 2.0, 2.0))
    ink.reveal_with(world, (90, 40))
    got = ink._revealed(0, 0, 8, 8)
    assert got[5, 5, 0] == 200 and got[4, 5, 0] == 0 and got[5, 4, 0] == 0
