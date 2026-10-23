"""Two things that would break silently: a layered sound (clips sharing a `group`) moves and re-levels together as
one undo step, and the compiler writes stretch / shift / plug-ins exactly as the engine contract has them."""
from rostrum_core import Document, Who

from rostrum_sound import KIND, compile, run_source

DOOR = """
tempo(120)
marker("hit", at=4.0)
d = track("door")
d.layer("door", [r"C:\\a\\thud.wav", {"media": r"C:\\a\\creak.wav", "volume": 0.5, "at": "#hit+0.5"}], at=2.0)
d.clip(r"C:\\a\\other.wav", at=8.0)
"""


def _doc():
    doc = Document.new(KIND)
    doc.run_script("door.py", run_source(DOOR, "door.py"), Who.script("door.py"))
    return doc


def test_a_layer_moves_and_levels_together_in_one_undo_step():
    doc = _doc()
    thud, creak, other = [c["id"] for c in doc.item("door")["clips"]]
    doc.apply({"op": "clip.set", "target": [thud], "args": {"at": 3.0, "volume": 0.5}}, Who.person())

    assert doc.item(thud)["at"] == 3.0
    assert doc.item(creak)["at"] == "#hit+1.5"                   # keeps its own way of writing the time
    assert doc.item(creak)["volume"] == 0.25 and doc.item(other)["at"] == 8.0 and doc.item(other)["volume"] == 1
    doc.apply({"op": "clip.set_one", "target": [creak], "args": {"volume": 1}}, Who.person())
    assert doc.item(thud)["volume"] == 0.5 and doc.item(creak)["volume"] == 1   # set_one touches only that clip
    doc.undo(Who.person())
    doc.undo(Who.person())                                         # one undo undoes the whole group move
    assert doc.item(thud)["at"] == 2.0 and doc.item(creak)["at"] == "#hit+0.5" and doc.item(creak)["volume"] == 0.5


def test_compile_writes_stretch_shift_and_plugins_as_the_contract():
    doc = _doc()
    clip = doc.item("door")["clips"][0]["id"]
    doc.apply({"op": "clip.set", "target": [clip], "args": {"stretch": 2, "shift": -3}}, Who.person())
    spec = {"format": "clap", "path": r"C:\p\Tape.clap", "id": "org.tape", "name": "Tape",
            "params": {"drive": 0.4, "mix": [[0, 0], ["#hit", 1]]}, "state": "AAEC"}
    doc.apply([{"op": "effect.add", "target": ["door"], "args": {"effect": "plugin", "plugin": spec}},
               {"op": "track.add", "args": {"id": "lead", "instrument": "plugin", "plugin": spec}}], Who.person())
    out = compile(doc)
    c = out["tracks"][0]["clips"][0]
    assert c["stretch"] == 2 and c["shift"] == -3 and "group" not in c
    assert out["tracks"][0]["effects"] == [{"type": "plugin", "format": "clap", "path": r"C:\p\Tape.clap",
                                            "id": "org.tape", "params": {"drive": 0.4, "mix": [[0, 0], [4.0, 1]]},
                                            "state": "AAEC"}]            # `name` is ours; marker times are seconds
    assert out["tracks"][1]["instrument"]["plugin"]["id"] == "org.tape"
