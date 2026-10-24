"""What agents and both timelines rely on in the time view (timeview.py): seconds <-> pixels round-trips, zooming at
the pointer keeps the moment under it, the view never leaves the timeline (zooming out all the way is fit again), an
edit's new length never moves the view (only the person does), and bad input is refused loudly."""
import pytest

from rostrum_gui.timeview import TimeView


def test_seconds_pixels_round_trip_and_zoom_keeps_the_pointer():
    v = TimeView(20.0)
    assert v.t_of(v.x_of(7.3, 800), 800) == pytest.approx(7.3)
    under = v.t_of(600, 800)                          # the moment under the pointer, 3/4 across
    v.zoom(4, 600 / 800)
    assert not v.fit and v.t_of(600, 800) == pytest.approx(under)
    assert v.t_of(v.x_of(13.1, 800), 800) == pytest.approx(13.1)


def test_view_stays_inside_and_fit_returns():
    v = TimeView(20.0)
    v.zoom(4, 0.9)
    v.scroll(100)
    assert v.start + v.span == pytest.approx(20.0)
    assert v.follow(2.0) and v.start <= 2.0 <= v.start + v.span
    v.set_length(4.0)                                 # an edit made it shorter than the view: spare room after the end
    assert not v.fit and v.start == 0 and v.span == pytest.approx(5.0)
    v.zoom(3, 0.5)
    v.zoom(0.01, 0.5)
    assert v.fit and v.span == 4.0


def test_an_edit_that_changes_the_length_never_moves_the_view():
    v = TimeView()
    v.set_length(20.0)                                # the first length is shown whole
    assert v.fit and v.span == 20.0
    v.set_length(24.0)                                # a note drawn past the end: the grid stays under the pointer
    assert v.start == 0 and v.span == 20.0 and v.x_of(13.0, 800) == pytest.approx(520)
    v.set_length(16.0)                                # a delete: still the same stretch, spare room after the end
    assert v.start == 0 and v.span == 20.0
    v.show_all()                                      # Fit, by the person
    assert v.fit and v.span == 16.0


def test_bad_input_is_refused():
    for bad in (lambda: TimeView(0), lambda: TimeView(20).zoom(0), lambda: TimeView(20).zoom(float("nan")),
                lambda: TimeView(20).t_of(10, 0)):
        with pytest.raises(ValueError):
            bad()
