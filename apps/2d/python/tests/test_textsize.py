"""A layout solved on every frame must not ask the engine per frame: a text is measured once per set of fields, and
a frame's texts go in one round trip (textsize.py)."""
from rostrum2d import textsize
from rostrum2d.evaluate import resolve


class CountingEngine:
    def __init__(self):
        self.calls = []

    def measure(self, items):
        self.calls.append([i["body"] for i in items])
        return {i["id"]: (10.0 * len(i["body"]), i["size"]) for i in items}


def test_unchanged_fields_are_measured_once_and_a_frame_in_one_trip():
    textsize._sizes.clear()
    eng = CountingEngine()
    a = resolve({"id": "a", "type": "text", "body": "Alpha"}, 0.0)
    b = resolve({"id": "b", "type": "text", "body": "Be"}, 0.0)
    with textsize.use(eng):
        textsize.prime([a, b, a])
        for _ in range(3):                                      # frame after frame, nothing changed
            assert textsize.size(a) == (50.0, a["size"]) and textsize.size(b) == (20.0, b["size"])
        textsize.size({**a, "color": "#ff0000"})                # what doesn't change the box isn't asked again
        textsize.size({**a, "weight": 300.0})                   # what does is
    assert eng.calls == [["Alpha", "Be"], ["Alpha"]]
