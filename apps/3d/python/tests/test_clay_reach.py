"""rostrum3d/clay_reach.py: a clay piece's blend joins only what it touches, decided per pair (gaps7 Hello: the head's
4 cm blend reached the shoulder 1 cm under it and webbed head and arm together; then holding the arm's one blend off the
head also creased its join to the body). The core gets the asked blend plus the balls of each piece it must ease off;
the document keeps the asked value."""
from rostrum3d.clay_scene import chain


def _piece(at, r, blend, to=None, name=""):
    s = {"step": "piece", "shape": "capsule" if to else "sphere", "mode": "add", "at": list(at), "radius": r, "blend": blend,
         "symmetry": "x", "name": name}
    if to:
        s["to"] = list(to)
    return s


def test_a_blend_eases_off_only_the_pieces_it_does_not_touch():
    body = _piece((0, 0.07, 0), 0.07, 0.035)
    head = _piece((0, 0.185, 0), 0.055, 0.012, name="head")               # overlaps the body
    arm = _piece((0.055, 0.12, 0), 0.02, 0.03, to=(0.19, 0.06, 0))        # touches the body, 1 cm under the head
    sent = chain([body, head, arm])
    assert sent[2]["blend"] == 0.03 and arm["blend"] == 0.03              # the arm's join to the body: as asked
    near = sent[2]["pairs"]
    assert near and all(len(q) == 5 and q[4] < 0.01 for q in near)        # eased to under the gap, near the head only
    assert {round(q[1], 3) for q in near} == {0.185}                       # the head's balls, not the body's
    assert "pairs" not in sent[1]                                          # the head touches the body only: as asked
    far = chain([body, _piece((0, 0.185, 0), 0.055, 0.012), _piece((0.06, 0.095, 0), 0.02, 0.01, to=(0.17, 0.02, 0))])
    assert all("pairs" not in s for s in far)                              # nothing near: as asked
