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


def test_a_designed_sound_layers_with_clips_and_a_bad_group_is_loud():
    """`group` on a designed sound (schema, S35): it moves with its clip layer; a group that isn't text is refused;
    a sound without one (every older file) is unchanged."""
    import pytest
    from rostrum_core import RostrumError
    doc = Document.new(KIND)
    doc.run_script("door.py", run_source(DOOR + 'd.sound("click", at=2.0, group="door")\nd.sound("hit", at=6.0)\n',
                                         "door.py"), Who.script("door.py"))
    thud = doc.item("door")["clips"][0]["id"]
    click, hit = [s["id"] for s in doc.item("door")["sounds"]]
    doc.apply({"op": "clip.set", "target": [thud], "args": {"at": 3.0}}, Who.person())
    assert doc.item(click)["at"] == 3.0 and doc.item(hit)["at"] == 6.0 and "group" not in doc.item(hit)
    doc.apply({"op": "sound.set", "target": [click], "args": {"at": 4.0}}, Who.person())     # and the other way round
    assert doc.item(thud)["at"] == 4.0
    with pytest.raises(RostrumError):
        doc.apply({"op": "sound.set", "target": [hit], "args": {"group": 5}}, Who.person())
    assert "group" not in compile(doc)["tracks"][0]["sounds"][0]          # the layer is ours, not the engine's
