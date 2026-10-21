"""A Sound render is the item's next version that the project list sees, and a failed one stays unfinished and
says where (HANDOFFS § 1). A note's touch fields follow its track (facts(item, doc)). No engine is run."""
from pathlib import Path

import pytest
from rostrum_core import Document, RostrumError, Who, project
from rostrum_sound import KIND, handoff


class FakeEngine:
    def __init__(self, fail=False):
        self.fail = fail

    def request(self, do, schedule, out, stems, stemsDir):
        if self.fail:
            raise RuntimeError("engine stopped")
        open(out, "wb").write(b"RIFF")
        stem = f"{stemsDir}/drums.wav"
        open(stem, "wb").write(b"RIFF")
        return {"file": out, "stems": {"drums": stem}, "seconds": 1.0, "lufs": -16.0, "truePeak": -1.2, "clipped": [],
                "tracks": [{"id": "drums", "lufs": -20.0, "peak": -3.0}]}


def test_a_render_is_a_version_and_a_failed_one_stays_partial(tmp_path):
    doc = Document.new(KIND, folder=tmp_path, item="song")
    doc.save()
    r = handoff.render(tmp_path, doc, FakeEngine(), {}, "agent:test")
    assert r["version"] == 1 and r["file"].endswith("v001\\song_mix.wav") or r["file"].endswith("v001/song_mix.wav")
    latest = project.latest_render(tmp_path, "song", "sound")
    assert latest["version"] == 1 and set(latest["files"]) == {"song_mix.wav", "drums.wav"}
    assert latest["manifest"]["stems"]["drums"]["loudness_lufs"] == -20.0

    with pytest.raises(RostrumError) as e:
        handoff.render(tmp_path, doc, FakeEngine(fail=True), {}, "agent:test")
    assert "v002.partial" in str(e.value)
    assert [v["version"] for v in project.renders(tmp_path, "song")] == [1]


def test_note_touch_follows_its_track():
    doc = Document.new(KIND)
    doc.apply([{"op": "track.add", "args": {"id": "gtr", "instrument": "model", "model": "guitar"}},
               {"op": "track.add", "args": {"id": "vln", "instrument": "model", "model": "violin"}}], Who.person())
    doc.apply([{"op": "note.add", "target": ["gtr"], "args": {"pitch": "E3", "at": 0, "dur": 1, "damping": 0.6}}],
              Who.person())
    with pytest.raises(RostrumError, match="damping"):
        doc.apply([{"op": "note.add", "target": ["vln"], "args": {"pitch": "E4", "at": 0, "dur": 1, "damping": 0.6}}],
                  Who.person())
    note = doc.item("gtr")["notes"][0]
    assert KIND.facts(note, doc)["plucked"] and not KIND.facts(note, doc)["articulated"]
