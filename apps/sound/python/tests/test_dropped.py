"""An older song holding a designed sound (no longer made, 2026-10-23) still opens; the sound is named in plain words
(DocKind.warn) and left out of the mix, never dropped silently."""
import json

from rostrum_core import Document

from rostrum_sound import KIND, compile, opening


def test_an_older_song_with_a_designed_sound_opens_and_says_so(tmp_path):
    doc = Document.new(KIND, folder=tmp_path, item="cue")
    doc.data["tracks"].append({"id": "fx", "type": "track",
                               "sounds": [{"id": "s1", "type": "sound", "design": "riser", "at": 2.0}]})
    doc.save()
    f = next(tmp_path.rglob("*.trk"))
    raw = json.loads(f.read_text())
    raw.pop("hash", None)                                   # as an older Rostrum wrote it
    f.write_text(json.dumps(raw))
    old = opening.open_whole(tmp_path, "cue")
    said = KIND.warnings(old.data)
    assert len(said) == 1 and said[0].startswith("fx:") and '"riser" at 2 s' in said[0]
    assert compile(old)["tracks"] == [{"id": "fx"}]
