"""K keys the whole pose when any of it changes: a setting holding still is keyed as a hold, so a move added later
starts there (production round, hand rows 1 / 24: a frame's zoom crept from 0 s because K skipped it)."""
from rostrum_core import Document, Who

from rostrum2d import KIND, run_source

AGENT = Who.agent("tester")


def _zoom_keys(d):
    return sorted(k["t"] for k in d.item("frame")["keys"] if k["prop"] == "zoom")


def test_k_holds_a_still_zoom_when_the_position_moves():
    d = Document.new(KIND)
    d.run_script("s.py", run_source('comp("c", fps=10, duration=20)\ncam = camera("cam")\ncam.key("zoom", {0: 1})\ncam.key("x", {0: 960})\n', "s.py"))
    d.apply({"op": "key.add", "target": ["frame"], "args": {"prop": "x", "t": 5, "v": 1300}}, AGENT)
    d.apply({"op": "key.add", "target": ["frame"], "args": {"fields": "pose", "t": 9.4}}, AGENT)
    assert _zoom_keys(d) == [0, 9.4]


def test_k_on_a_pose_that_holds_everywhere_still_changes_nothing():
    d = Document.new(KIND)
    d.run_script("s.py", run_source('comp("c", fps=10, duration=20)\ncam = camera("cam")\n', "s.py"))
    d.apply({"op": "key.add", "target": ["frame"], "args": {"fields": "pose", "t": 0}}, AGENT)
    before = len(d.item("frame")["keys"])
    try:
        d.apply({"op": "key.add", "target": ["frame"], "args": {"fields": "pose", "t": 3}}, AGENT)
    except Exception:  # noqa: BLE001  refused in words: nothing new to key
        pass
    assert len(d.item("frame")["keys"]) == before
