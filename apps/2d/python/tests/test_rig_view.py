"""The rig eyes read the engine's `bones` reply correctly: a sliding pinned foot is reported, a held one is not;
the overlay draws on the frame. (The engine reply is faked; the lead runs the real tools after the build.)"""
from PIL import Image

from rostrum2d.mcp import rig_view

PIN = [{"t": 0, "v": 0, "ease": "hold", "prop": "pin"}, {"t": 0.2, "v": 1, "ease": "hold", "prop": "pin"},
       {"t": 0.6, "v": 0, "ease": "hold", "prop": "pin"}]
RIG = {"id": "puppet", "type": "rig", "iks": [{"id": "legL", "bone": "shinL", "keys": PIN}]}
COMP = {"id": "main", "layers": [RIG]}


def reply(t, tip_x, gap=0.0):
    return {"puppet": {"bones": {"shinL": {"x": 10, "y": 10, "tipX": tip_x, "tipY": 50, "angle": 90}},
                       "iks": {"legL": {"targetX": 20, "targetY": 50, "gap": gap}}}}


def samples(tip_x_of):
    return [{"t": i / 10, "rigs": reply(i / 10, tip_x_of(i / 10), 0.3 if i == 4 else 0.0)} for i in range(8)]


def test_sliding_foot_is_reported_and_planted_is_not():
    slide = rig_view.chain_facts(samples(lambda t: 20 + (t - 0.2) * 10), RIG, "legL", "puppet", "t")
    planted = rig_view.chain_facts(samples(lambda t: 20.0), RIG, "legL", "puppet", "t")
    (span,) = slide["pinned_spans"]
    assert (span["start"], span["end"]) == (0.2, 0.5) and span["sliding"] and span["tip_moved_px"] == 3.0
    assert not planted["pinned_spans"][0]["sliding"]
    assert planted["largest_gap_px"] == 0.3 and planted["largest_gap_at"] == 0.4


def test_overlay_draws_on_the_frame(tmp_path):
    src, dest = tmp_path / "a.png", tmp_path / "b.png"
    Image.new("RGB", (100, 100), (0, 0, 0)).save(src)
    w, h = rig_view.draw_skeleton(src, reply(0.3, 10), COMP, 0.3, dest, 100)    # t=0.3: pinned, so the target is green
    img = Image.open(dest)
    assert (w, h) == (100, 100) and img.getpixel((10, 30)) == rig_view.BONE and img.getpixel((20, 50)) == rig_view.PINNED
