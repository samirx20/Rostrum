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
