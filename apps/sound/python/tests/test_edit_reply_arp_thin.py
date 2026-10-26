"""An arpeggio never drops a chord tone (2026-10-26: rate 0.5 on 3-note chords of one beat lost the third tone, reply
"Applied"); note.thin keeps every Nth per track or drops the soft ones; the edit reply names what changed."""
import pytest
from rostrum_core import Document, Who
from rostrum_core.mcp.edit_summary import sentence, summarize

from rostrum_sound import KIND

P = Who.person()


def _op(op, target, **args):
    return {"op": op, "target": target, "args": args}


def _doc(*calls):
    d = Document.new(KIND)
    d.apply([_op("doc.set", ["root"], tempo=120), _op("track.add", [], id="t", instrument="builtIn", builtIn="piano"), *calls], P)
    return d


@pytest.mark.parametrize("rate", [0.25, 0.5, 1])
@pytest.mark.parametrize("mode", ["up", "upDown", "random"])
@pytest.mark.parametrize("tones", [["C4", "E4", "G4"], ["C4", "E4", "G4", "B4"]])
def test_arpeggio_plays_every_chord_tone(rate, mode, tones):
    adds = [_op("note.add", ["t"], id=f"{k}_{p}", pitch=p, at={"beat": 4 * k}, dur={"beats": 1}) for k in range(2) for p in tones]
    d = _doc(*adds)
    d.apply(_op("note.arpeggiate", [a["args"]["id"] for a in adds], rate=rate, mode=mode), P)
    for k in range(2):
        got = {n["pitch"] for n in d.item("t")["notes"] if 4 * k <= n["at"]["beat"] < 4 * k + 1}
        assert set(tones) <= got


def test_thin_keeps_every_other_and_drops_soft_and_the_reply_counts():
    d = _doc(*[_op("note.add", ["t"], id=f"n{i}", pitch="C4", at={"beat": i}, dur={"beats": 1}, vel=0.2 if i % 3 == 0 else 0.9) for i in range(8)])
    ch = d.apply(_op("note.thin", ["n0", "n1", "n2", "n3", "n4", "n5", "n6", "n7"], keep_every=2, offset=1), P)
    assert [n["id"] for n in d.item("t")["notes"]] == ["n1", "n3", "n5", "n7"]
    text = sentence(summarize(d, ch))
    assert "Removed 4 notes" in text and "Kept 4 of the 8 targeted" in text and "n0 at 0.00 s C4" in text
    d.apply(_op("note.thin", ["n1", "n3", "n5", "n7"], below_vel=0.5), P)
    assert [n["id"] for n in d.item("t")["notes"]] == ["n1", "n5", "n7"]
