"""The two things the Sound document must never get wrong silently: a script re-run keeps a person's edit, and
the compiler's schedule has the engine contract's shape (with marker references resolved)."""
from rostrum_core import Document, Who

from rostrum_sound import KIND, compile, run_source

CUE = """
tempo(120)
marker("drop", at=bar(3))
pad = track("pad", builtIn="warmPad", volume=0.6)
pad.chord(["D3", "A3", "F4"], at=beat(0), dur=beats(4))
pad.note("D4", at="#drop+0.5", dur=1.0, vel=0.6)
kit = track("drums", kit="synth")
kit.hit("kick", at=beat(0))
master(loudness=-16)
"""


def test_rerun_keeps_a_persons_level():
    doc = Document.new(KIND)
    doc.run_script("cue.py", run_source(CUE, "cue.py"), Who.script("cue.py"))
    doc.apply({"op": "track.set", "target": ["pad"], "args": {"volume": 0.3}}, Who.person())

    changed = CUE.replace("volume=0.6", "volume=0.9").replace('kit.hit("kick", at=beat(0))',
                                                             'kit.hit("kick", at=beat(0)); kit.hit("snare", at=beat(1))')
    report = doc.run_script("cue.py", run_source(changed, "cue.py"), Who.script("cue.py"))

    assert doc.item("pad")["volume"] == 0.3                       # the person's level is kept …
    assert [h["key"] for h in report.held] == ["pad.volume"]      # … and reported
    assert [h["drum"] for h in doc.item("drums")["hits"]] == ["kick", "snare"]   # the script's other change lands


def test_compile_has_the_contract_shape():
    doc = Document.new(KIND)
    doc.run_script("cue.py", run_source(CUE, "cue.py"), Who.script("cue.py"))
    s = compile(doc)

    assert s["contract"] == "rostrum-sound-schedule/1" and s["tempo"] == 120
    pad, drums = s["tracks"]
    assert pad["id"] == "pad" and pad["instrument"] == {"builtIn": "warmPad"}
    assert all({"pitch", "at", "dur"} <= set(n) for n in pad["notes"])
    assert pad["notes"][1]["at"] == 4.5                           # "#drop+0.5": bar 3 at 120 bpm = 4 s, + 0.5
    assert drums["instrument"] == {"kit": "synth"} and drums["hits"][0]["drum"] == "kick"
    assert s["master"]["loudness"] == -16 and s["master"]["truePeak"] == -1


PLAYED = """
tempo(120)
s = track("vln", builtIn="analogStrings")
for i in range(8):
    s.note("D4", at=i * 0.5, dur=0.4)
s.phrase(0, 3.5, vel=[(0, 0.4), (1, 0.9)])
s.humanize(seed=5, timing=0.01, velocity=0.05)
"""


def test_humanize_is_the_same_every_run_and_keeps_a_persons_move():
    first, again = run_source(PLAYED, "p.py"), run_source(PLAYED, "p.py")
    notes = first["tracks"][0]["notes"]
    assert notes == again["tracks"][0]["notes"]                                # same seed -> same ids and values
    assert len({n["at"] for n in notes}) == 8 and any(n["at"] != i * 0.5 for i, n in enumerate(notes))

    doc = Document.new(KIND)
    doc.run_script("p.py", first, Who.script("p.py"))
    moved = notes[3]["id"]
    doc.apply({"op": "note.set", "target": [moved], "args": {"at": 9.0, "vel": 0.2}}, Who.person())
    doc.run_script("p.py", run_source(PLAYED.replace("range(8)", "range(9)"), "p.py"), Who.script("p.py"))
    assert doc.item(moved)["at"] == 9.0 and doc.item(moved)["vel"] == 0.2     # the person's move is kept
    assert len(doc.item("vln")["notes"]) == 9                                  # the script's new note lands


def test_touch_fields_follow_the_model():
    from rostrum_core.conditions import holds
    from rostrum_sound.doc import fields as FD
    shown = {p.name: p.valid_when for p in FD.params("track")}

    def visible(**track):
        values = {**FD.DEFAULTS["track"], **track}
        return {k for k in ("position", "damping", "hardness", "attack") if holds(shown[k], values)}
    assert visible(instrument="model", model="guitar") == {"position", "damping", "hardness"}
    assert visible(instrument="model", model="marimba") == {"position", "hardness"}     # no damping on bars
    assert visible(instrument="model", model="violin") == set()
    assert visible(instrument="synth") == {"attack"}


ROUTED = """
tempo(120)
voice = track("voice", builtIn="feltPiano", volume=0.8)
voice.note("D4", at=0, dur=1.0)
pad = track("pad", builtIn="warmPad")
pad.note("D3", at=0, dur=2.0)
"""


def _person(doc, op, target=None, **args):
    doc.apply({"op": op, **({"target": [target]} if target else {}), "args": args}, Who.person())


def test_buses_sends_and_ducks_compile_and_a_rerun_keeps_them():
    import pytest
    from rostrum_core import RostrumError

    doc = Document.new(KIND)
    doc.run_script("r.py", run_source(ROUTED, "r.py"), Who.script("r.py"))
    _person(doc, "bus.add", id="reverb", name="Reverb")
    _person(doc, "effect.add", "reverb", effect="reverb")
    _person(doc, "bus.add", id="music", name="Music")
    _person(doc, "send.add", "pad", bus="reverb", level=0.4)
    _person(doc, "track.set", "pad", output="music")
    _person(doc, "duck.add", "pad", under=["voice"], depth=0.7)
    _person(doc, "automation.set", "pad.send_reverb", lane="level", points=[[0, 0.1], [2, 0.5]])
    doc.run_script("r.py", run_source(ROUTED, "r.py"), Who.script("r.py"))          # the script runs again

    s = compile(doc)
    pad = next(t for t in s["tracks"] if t["id"] == "pad")
    assert [b["id"] for b in s["buses"]] == ["reverb", "music"] and s["buses"][0]["effects"][0]["type"] == "reverb"
    assert pad["output"] == "music" and pad["sends"] == [{"bus": "reverb", "level": [[0, 0.1], [2, 0.5]], "pre": False}]
    assert pad["ducks"][0]["under"] == ["voice"] and pad["ducks"][0]["depth"] == 0.7
    assert "output" not in next(t for t in s["tracks"] if t["id"] == "voice")

    with pytest.raises(RostrumError, match="still used"):                          # loud, never a silent mute
        _person(doc, "bus.remove", "reverb")
    with pytest.raises(RostrumError, match="not master or a bus"):
        _person(doc, "track.set", "pad", output="nowhere")


def test_a_script_sets_vibrato_rate_after_its_vibrato_lane():
    # valid_when facts (a vibrato lane) hold in the script layer too (P4's cue broke on this, found in P5).
    src = 't = track("v", builtIn="warmPad")\nt.note("A3", at=0, dur=1)\nt.vibrato([(0, 0.0), (1, 0.5)], rate=5.2, depth=10)\n'
    doc = Document.new(KIND)
    doc.run_script("v.py", run_source(src, "v.py"), Who.script("v.py"))
    assert compile(doc)["tracks"][0]["expression"]["vibratoRate"] == 5.2


def test_removing_a_used_marker_is_refused_after_other_edits():
    """The check looks only at changed items while the markers stay the same (check.py _ref_holders); a marker
    removed under a note that points at it must still fail loudly."""
    import pytest
    from rostrum_core import RostrumError
    doc = Document.new(KIND)
    doc.run_script("cue.py", run_source(CUE, "cue.py"), Who.script("cue.py"))
    doc.apply({"op": "track.set", "target": ["pad"], "args": {"volume": 0.3}}, Who.person())   # the fast path
    drop = next(m["id"] for m in doc.data["markers"] if m.get("name") == "drop")
    with pytest.raises(RostrumError, match="drop"):
        doc.apply({"op": "marker.remove", "target": [drop], "args": {}}, Who.person())
