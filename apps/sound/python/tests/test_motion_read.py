"""Sounds from motion: several layers making one gesture together are one event (7 cards landing on one frame were 7
stacked clicks, +15 dBFS, in the P19 film), and a slow drift gets no whoosh."""
from rostrum_sound.motion import read, score


def _layer(x0, x1, n=60, start=10, end=30):
    xs = [x0 + (x1 - x0) * min(1, max(0, (i - start) / (end - start))) for i in range(n)]
    return {"x": xs, "y": [500.0] * n, "scale": [1.0] * n, "opacity": [1.0] * n, "w": 100, "h": 100}


def test_one_gesture_from_many_layers_is_one_event_and_drifts_are_silent():
    layers = {f"card{i}": _layer(100.0, 900.0) for i in range(7)}
    layers["drift"] = _layer(100.0, 200.0, start=0, end=59)      # ~100 px/s: seen as a move, too slow to whoosh
    evs = read.events({"rate": 60, "width": 1920, "height": 1080, "layers": layers})
    moves = {tuple(sorted(e["layers"])): e for e in evs if e["kind"] == "move"}
    cards = tuple(sorted(layers.keys() - {"drift"}))
    assert set(moves) == {cards, ("drift",)} and moves[cards]["area"] == 7 * 100 * 100
    whooshes = [s for t, s in score.sounds(evs, 1920, 1080) if s["design"] == "whoosh"]
    assert len(whooshes) == 1
