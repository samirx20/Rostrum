"""The key timeline's operations work on any app's items (rostrum_core.keys.anim_ops): a stand-in 3D-like object's keys,
read with animations() and eased with anim.ease from a script, in one undo step; its last key starts no stretch."""
import pytest
from rostrum_core import Document, Param, Registry, Who
from rostrum_core.errors import RostrumError
from rostrum_core.keys import Names, animations, register_anim_ops, register_key_ops
from rostrum_core.kind import DocKind

SAM = Who.person("sam")
R = Registry()


def _number(ctx, owner, prop, args):
    return "v", float(args["v"])


@R.operation("object.add", "Add an object", target="doc", params=[Param.text("id", label="Id", required=True)])
def object_add(ctx, targets, args):
    ctx.insert("root", "objects", {"id": args["id"], "type": "object", "visible": True, "keys": []}, None)


put_key = register_key_ops(R, owners=["object"], check_key=_number, check_still=lambda ctx, o, p, a: float(a["v"]))
NAMES = Names(pairs={"location": ("lx", "ly", "lz")}, labels={"location": "Location"}, words={"location": "Move"})
register_anim_ops(R, owners=["object"], put_key=put_key, names=NAMES)
KIND = DocKind("scene3d", ".s3d", R, lists={"doc": ["objects"], "object": ["keys"]},
               new=lambda: {"id": "root", "type": "doc", "objects": []})


@pytest.fixture
def doc():
    d = Document.new(KIND)
    d.apply([{"op": "object.add", "target": "root", "args": {"id": "cube"}},
             *[{"op": "key.add", "target": "cube", "args": {"prop": p, "t": t, "v": v}}
               for p in ("lx", "ly") for t, v in ((0.0, 0), (1.0, 2), (2.0, 5))]], SAM)
    return d


def test_a_script_eases_a_3d_objects_stretch(doc):
    anim, = animations(doc.item("cube"), NAMES)
    assert anim["setting"] == "location" and anim["word"] == "Move" and anim["props"] == ["lx", "ly"] and len(anim["stretches"]) == 2
    first = anim["stretches"][0]["ids"]
    assert sorted(first) == ["cube.lx.k0", "cube.ly.k0"]
    doc.apply({"op": "anim.ease", "target": first, "args": {"preset": "bounce"}}, SAM)
    assert all(doc.item(k)["ease"] == "bounce" for k in first)
    assert doc.item("cube.lx.k1000")["ease"] == "smooth"                     # the next stretch is left alone
    doc.undo(SAM)
    assert all(doc.item(k)["ease"] == "smooth" for k in first)               # one change, one undo


def test_the_last_key_starts_no_stretch(doc):
    with pytest.raises(RostrumError, match="last key"):
        doc.apply({"op": "anim.ease", "target": ["cube.lx.k2000"], "args": {"preset": "linear"}}, SAM)


def test_an_on_off_field_stays_true_false_when_its_keys_go(doc):
    """A toggle's key holds 1.0 / 0.0; stopping the animation or deleting its last key writes back True / False."""
    for t, v in ((0.0, 1.0), (1.0, 0.0)):
        doc.apply([{"op": "key.add", "target": "cube", "args": {"prop": "visible", "t": t, "v": v}}], SAM)
    doc.apply([{"op": "key.clear", "target": "cube", "args": {"prop": "visible", "at": 2.0}}], SAM)
    assert doc.item("cube")["visible"] is False
    doc.apply([{"op": "key.add", "target": "cube", "args": {"prop": "visible", "t": 0.0, "v": 1.0}}], SAM)
    doc.apply([{"op": "key.remove", "target": "cube.visible.k0"}], SAM)
    assert doc.item("cube")["visible"] is True
