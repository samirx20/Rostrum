"""rostrum3d/clay_reach.py: a clay piece's blend joins only what it touches (gaps7 Hello: the head's 4 cm blend reached
the shoulder 1 cm under it and webbed head and arm together); the engine gets the held blend, the document keeps the asked one."""
from rostrum3d.clay_scene import chain


def _piece(at, r, blend, to=None, name=""):
    s = {"step": "piece", "shape": "capsule" if to else "sphere", "mode": "add", "at": list(at), "radius": r, "blend": blend,
         "symmetry": "x", "name": name}
    if to:
        s["to"] = list(to)
    return s


def test_a_blend_never_reaches_a_piece_it_does_not_touch_and_joins_one_it_does():
    body = _piece((0, 0.07, 0), 0.07, 0.035)
    head = _piece((0, 0.185, 0), 0.055, 0.04, name="head")                 # overlaps the body
    arm = _piece((0.055, 0.12, 0), 0.02, 0.01, to=(0.19, 0.06, 0))         # 1 cm under the head
    sent = chain([body, head, arm])
    assert sent[1]["blend"] < 0.01 and head["blend"] == 0.04, sent[1]      # held off the arm; the document keeps 4 cm
    far = chain([body, _piece((0, 0.185, 0), 0.055, 0.012), _piece((0.06, 0.095, 0), 0.02, 0.01, to=(0.17, 0.02, 0))])
    assert far[1]["blend"] == 0.012                                        # nothing near: as asked
