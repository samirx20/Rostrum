"""A refine export left at the defaults is never quietly worse than the last export of the shot; one the agent set lower
(the call's quality / samples, or the shot's own Quality) is done as written, with a note saying what it loses."""
from rostrum3d import render_last as RL

K = ("proj", "shot", "hero")


def setup_function():
    RL._LAST.clear()
    RL.remember(K, "cycles", {"samples": 512, "denoise": True})


def test_left_at_the_defaults_it_renders_as_the_last_export():
    renderer, cycles, note = RL.keep(K, "cycles", {"samples": 128, "denoise": True}, {}, "good")
    assert cycles["samples"] == 512 and "as your last export" in note


def test_a_shot_quality_set_lower_is_never_overridden():
    renderer, cycles, note = RL.keep(K, "cycles", {"samples": 32, "denoise": True}, {}, "draft")
    assert cycles["samples"] == 32 and "Done as the shot's Quality (draft) says" in note


def test_a_call_asking_lower_is_done_as_asked():
    renderer, cycles, note = RL.keep(K, "cycles", {"samples": 64, "denoise": True}, {"samples": 64}, "good")
    assert cycles["samples"] == 64 and "Done as asked" in note
