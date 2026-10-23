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


def test_diagnose_lists_an_outside_file_and_names_a_missing_one(tmp_path):
    from rostrum_core import Who
    from rostrum_sound import diagnose
    outside = tmp_path / "elsewhere" / "kept.wav"
    outside.parent.mkdir()
    outside.write_bytes(b"RIFF")
    doc = Document.new(KIND, folder=tmp_path / "song", item="cue")
    doc.apply([{"op": "track.add", "args": {"id": "dlg"}},
               {"op": "clip.add", "target": ["dlg"], "args": {"id": "far", "media": str(outside), "at": 0.0}},
               {"op": "clip.add", "target": ["dlg"], "args": {"id": "lost", "media": "media/gone.wav", "at": 1.0}}], Who.person())
    found = {p["item"]: p for p in diagnose.problems(doc)}
    assert found["far"]["kind"] == "outside-project" and "kept.wav" in found["far"]["message"]
    assert found["lost"]["kind"] == "missing-file" and "media/gone.wav" in found["lost"]["message"]
