"""look_motion (mcp/motion_look.py) is what an agent relies on to catch a bud passing through its case, a snap, an item
leaving the picture; it reads the document only (no engine), so a wrong frame or a missing name would go unnoticed."""
from rostrum_core import Document, Who
from rostrum_core.mcp import App, Runtime

from rostrum3d import KIND, run_source
from rostrum3d.mcp import motion_look

AGENT = Who.agent("tester")
SRC = '''
camera("cam", z=3)
mesh("case", shape="box", width=0.2, height=0.1, depth=0.1)
mesh("bud", shape="sphere", radius=0.03, y=0.02).key("x", {0: -0.6, 1: 0.6}, ease="linear")
mesh("puck", shape="box", width=0.1, height=0.1, depth=0.1, y=-0.5).key("x", {0: 0, 0.5: 0, 0.54: 2}, ease="linear")
shot("hero", camera="cam", fps=24, start=0, end=1)
'''


def call(args: dict, src: str = SRC):
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(src, "s.py"))
    return Runtime(App("rostrum-3d", {"scene": doc}), motion_look.tools).call("look_motion", args, AGENT)[0]


def test_a_bud_passing_through_its_case_is_named_with_both_items_and_the_frames():
    reply = call({})
    assert reply["ok"], reply
    hit = [f for f in reply["data"]["findings"] if f["kind"] == "passes_through" and "bud" in f["items"]]
    assert len(hit) == 1 and hit[0]["items"] == ["case", "bud"]
    # x = -0.6 + 0.05 a frame: the sphere (radius 0.03) is inside the case's box (half width 0.1) for |x| < 0.13: frames 10-14
    assert hit[0]["frames"] == [10, 14], hit
    text = reply["summary"]
    assert "case and bud overlap" in text and "frames 10–14" in text
    assert "renderer: none" in text and "oriented boxes" in text and "frames 0–23" in text
    jumps = [f for f in reply["data"]["findings"] if f["kind"] == "jumps"]
    assert [(j["item"], j["frames"]) for j in jumps] == [("puck", [12, 13])]
    out = [(f["item"], f["how"], f["frames"]) for f in reply["data"]["findings"] if f["kind"] == "leaves_frame"]
    assert out == [("puck", "wholly", [13, 23])]          # 2 m to the side, 3 m in front of a 50 mm lens: past the edge


def test_unknown_item_too_few_frames_and_nothing_moving_fail_with_the_reason():
    assert reply_error(call({"items": ["earbud"]})) == "NOT_FOUND"
    assert reply_error(call({"frames": [5, 5]})) == "BAD_ARGUMENT"
    still = SRC.replace('.key("x", {0: -0.6, 1: 0.6}, ease="linear")', "").replace('.key("x", {0: 0, 0.5: 0, 0.54: 2}, ease="linear")', "")
    out = call({}, still)
    assert reply_error(out) == "NOT_FOUND" and "nothing moves" in str(out)


def reply_error(reply: dict) -> str:
    assert not reply["ok"], reply
    return reply["error"]["code"]
