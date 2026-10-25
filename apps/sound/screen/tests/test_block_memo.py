"""A note's block re-placed instead of made again (a tempo let go, a whole-song Right, its undo: block_memo.made's
`again`) must be exactly the block made from nothing: one wrong second or a sharp spelled as a flat would show a
note where it is not, and nothing else would catch it."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document, Who  # noqa: E402
from rostrum_sound import KIND, run_source  # noqa: E402
from screensound import timeline  # noqa: E402
from screensound.block_memo import BlockMemo  # noqa: E402

SRC = '''
tempo(120)
tempo_change(beat(8), 90, ramp=True)
tempo_change(beat(16), 140)
tempo_change(6.0, 100)
key("C major")
key("D minor", at=beat(10))
key("Eb major", at=5.0)
marker("drop", beat(12))
lead = track("lead", builtIn="feltPiano")
bass = track("bass", builtIn="feltPiano")
for i in range(40):
    lead.note(["C4", "A#4", "F#4", ["D4", "Bb4"]][i % 4], at=beat(i * 0.5), dur=beats(0.5) if i % 3 else 0.3)
    bass.note("A#2", at=float(i) * 0.25 if i % 2 else beat(i * 0.75), dur=beats(1))
lead.note("G4", at="#drop+0.5", dur=until("#drop+2"))
bass.note("C#3", at=beat(1), dur="next")
'''


def fresh(root):
    return [b for t in root["tracks"] for b in timeline.blocks(t, root)]


def shown(memo, root):
    memo.follow(timeline.clock(root), {t["id"] for t in root["tracks"]})
    return [b for t in root["tracks"] for b in timeline.blocks(t, root, memo)]


def test_re_placed_blocks_are_the_blocks_made_from_nothing():
    doc, who, rnd = Document.new(KIND), Who.person(), random.Random(7)
    doc.run_script("song.py", run_source(SRC, "song.py"))
    memo = BlockMemo()
    assert shown(memo, doc.data) == fresh(doc.data)
    tempos = [t["id"] for t in doc.data["tempos"]]
    notes = [n["id"] for t in doc.data["tracks"] for n in t["notes"]]
    for step in range(30):
        if step % 3 == 0:          # the song's tempo, or one change's tempo or glide
            doc.apply([{"op": "doc.set", "target": ["root"], "args": {"tempo": rnd.uniform(60, 180)}}], who)
        elif step % 3 == 1:
            doc.apply([{"op": "tempo.set", "target": [rnd.choice(tempos)],
                        "args": {"bpm": rnd.uniform(60, 180), "ramp": rnd.random() < 0.5}}], who)
        else:                      # notes moved (across the key changes) or the move undone
            some = rnd.sample(notes, 12)
            if rnd.random() < 0.3 and doc.history.changes:
                doc.undo(who)
            else:
                doc.apply([{"op": "note.move", "target": some, "args": {"by": {"beats": rnd.choice([-1, 0.5, 2, 3.25])}}}], who)
        assert shown(memo, doc.data) == fresh(doc.data), step
