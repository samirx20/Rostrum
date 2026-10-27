"""What would break silently: Play answers on the press (critic r12, interaction plan S4). The Play button says
"playing" in the press's own frame, also while the first render is still being made; the playhead runs from the press
time before the engine's first report; a refused render does not leave the button on "playing"; Space–Space always
stops (the second press is a stop, whatever the engine has done by then)."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_play_after_edit import bridge, pump  # noqa: E402,F401  (a song, a slow stand-in engine, a stand-in player)


def test_the_press_shows_playing_and_the_playhead_runs_from_it_before_the_engine_reports(bridge):  # noqa: F811
    tr = bridge.transport
    t0 = bridge._t
    bridge.togglePlay()
    assert tr.playing and bridge.playing                       # in the same call, before anything is pumped
    tr.player.rolled = False                                   # the engine has not said it is rolling
    time.sleep(0.12)
    tr._advance()
    assert bridge._t >= t0 + 0.1                               # the playhead left the press time on its own clock
    bridge.togglePlay()
    assert not tr.playing and not bridge.playing               # Stop lands at once


def test_space_space_quickly_stops_even_while_the_first_sound_is_made(bridge):  # noqa: F811
    tr = bridge.transport
    tr.last = {}                                               # nothing to play yet: the press waits for the render
    bridge._apply([{"op": "doc.set", "target": ["root"], "args": {"tempo": 90}}], "Tempo")
    bridge.togglePlay()
    assert tr.playing and tr._want                             # the button already shows it
    bridge.togglePlay()
    assert not tr.playing and not tr._want                     # the second press is a stop
    pump(10, lambda: not tr.busy())
    assert not tr.playing                                      # and the render landing starts nothing


def test_a_refused_render_does_not_leave_the_button_on_playing(bridge):  # noqa: F811
    tr = bridge.transport
    tr.last = {}
    bridge._apply([{"op": "doc.set", "target": ["root"], "args": {"tempo": 90}}], "Tempo")
    bridge.togglePlay()
    assert tr.playing
    tr._failed("Error: render: refused")
    assert not tr.playing
