"""A new text must be readable where it is made: dark ink on a light spot, white on a dark one (text_ink.py)."""
from screen2d.text_ink import DARK, LIGHT, ink_for


def test_ink_follows_what_is_under_the_text():
    assert ink_for("#d9d9d9") == DARK          # the new-shape grey
    assert ink_for("#202020") == LIGHT
    assert ink_for("", "#0a0f1a") == LIGHT     # nothing painted there: the background decides
    assert ink_for("", "#ffffff") == DARK
