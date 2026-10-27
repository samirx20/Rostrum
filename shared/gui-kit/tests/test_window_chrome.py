"""The merged title bar's hit test (window_chrome.hit_test): the one piece that breaks silently. A button missing from
it is dead (its click moves the window); a wrong band steals clicks from the bar's top pixels."""
import pytest

W, BAND = 1600, 5
MAX = (1508, 0, 46, 40)                      # minimise 1462-1508, maximise 1508-1554, close 1554-1600
ZONES = [(12, 8, 30, 24), (1462, 0, 46, 40), (1554, 0, 46, 40)]   # the mark-menu, minimise, close


def hit(x, y, maximised=False):
    from rostrum_gui.window_chrome import hit_test
    return hit_test(x, y, W, maximised, 0 if maximised else BAND, ZONES, MAX)


@pytest.mark.parametrize("x, y, maximised, code", [
    (600, 20, False, 2),      # a gap in the bar: drag (HTCAPTION)
    (20, 20, False, 1),       # the mark-menu: a click (HTCLIENT)
    (1530, 20, False, 9),     # the maximise button: Windows' own (HTMAXBUTTON, snap layouts)
    (1480, 20, False, 1),     # minimise and close: plain clicks
    (1599, 39, False, 1),
    (600, 2, False, 12),      # the top band resizes (HTTOP) ...
    (2, 2, False, 13),        # ... HTTOPLEFT in the corner
    (20, 2, False, 12),       # the band is above the mark-menu's zone, never inside it
    (1470, 2, False, 1),      # ... but not over the window buttons
    (1530, 2, False, 9),
    (1599, 0, False, 1),
    (600, 2, True, 2),        # maximised: no band, the top edge drags the window back out
    (1599, 0, True, 1),       # maximised: the screen's corner pixel is Close
    (600, 40, False, 1),      # below the bar: the app's own
    (20, 300, False, 1),
])
def test_hit(x, y, maximised, code):
    assert hit(x, y, maximised) == code


def test_no_buttons_keeps_the_band_to_the_right_corner():
    from rostrum_gui.window_chrome import hit_test
    assert hit_test(1598, 1, W, False, BAND, [], ()) == 14     # HTTOPRIGHT
    assert hit_test(800, 20, W, False, BAND, [], ()) == 2
