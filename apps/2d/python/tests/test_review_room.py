"""review_room names the Tally faults the blind judges saw: a caption past the frame edge, a wordmark crowding its logo,
a cursor floating outside the phone, a wipe circle parked as a dot; light_shafts fade to fully clear."""
from rostrum2d.mcp import review_room
from rostrum2d.script import run_source

SRC = '''
comp("main", width=1920, height=1080, fps=30, duration=6, background="#ffffff")
text("cap", body="Tally does the math.", size=64, weight=800, x=1625, y=500, align="center")
scr = device("phone", kind="phone", x=700, y=540, w=440, h=900)
cur = shape("cursor", shape="ellipse", w=50, h=50, x=700, y=540, fill="#000000")
cur.key("x", {0: 700, 3: 700, 4: 1100})
dot = shape("wipe", shape="ellipse", w=10, h=10, x=960, y=540, fill="#5b4bff")
dot.key("w", {4: 10, 5.5: 3000}); dot.key("h", {4: 10, 5.5: 3000})
with group("logo", x=1500, y=850, w=200, h=200):
    shape("logo_sq", w=200, h=200, x=100, y=100, fill="#5b4bff")
text("wordmark", body="Tally", size=120, weight=800, x=1600, y=1010)
'''


def test_names_each_fault():
    comp = run_source(SRC, "t.py")["comps"][0]
    step = 0.5
    rows = review_room.facts(comp, [i * step for i in range(12)], step)
    got = {(r["kind"], r["id"]) for r in rows}
    assert ("text_edge", "cap") in got
    assert ("outside", "cursor") in got
    assert ("speck", "wipe") in got
    assert ("crowded", "wordmark") in got


def test_shafts_fade_to_clear():
    root = run_source('comp("main", duration=4)\nlight_shafts("rays", count=3, strength=0.5)', "s.py")
    shafts = next(l for l in root["comps"][0]["layers"] if l["id"] == "rays")["layers"]
    assert len(shafts) == 3
    for s in shafts:
        assert s["fillType"] == "linear" and s["blend"] == "add"
        assert s["stops"][0]["opacity"] > 0.3 and s["stops"][-1]["opacity"] == 0.0
