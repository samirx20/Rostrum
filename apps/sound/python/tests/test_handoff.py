"""A Sound render is the item's next version that the project list sees, and a failed one stays unfinished and
says where (HANDOFFS § 1). A note's touch fields follow its track (facts(item, doc)). No engine is run."""
import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from rostrum_core import Document, RostrumError, Who, project
from rostrum_sound import KIND, handoff


class FakeEngine:
    """Writes real float files like the engine: a 440 Hz tone in the first 1.5 s, silence to 4 s (a 4 s song)."""
    def __init__(self, fail=False):
        self.fail = fail

    def request(self, do, schedule, out, stems, stemsDir):
        if self.fail:
            raise RuntimeError("engine stopped")
        rate = schedule.get("sampleRate", 48000)
        t = np.arange(4 * rate) / rate
        tone = (0.5 * np.sin(2 * np.pi * 440 * t) * (t < 1.5))[:, None].repeat(2, 1).astype("float32")
        sf.write(out, tone, rate, subtype="FLOAT")
        stem = f"{stemsDir}/drums.wav"
        sf.write(stem, tone * 0.5, rate, subtype="FLOAT")
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


def test_the_chosen_format_is_written_and_the_silent_end_is_cut_from_every_file(tmp_path):
    doc = Document.new(KIND, folder=tmp_path, item="song")
    doc.apply([{"op": "track.add", "args": {"id": "drums", "name": "Big: Drums/1", "instrument": "model", "model": "guitar"}}], Who.person())
    doc.save()
    r = handoff.render(tmp_path, doc, FakeEngine(), {}, "agent:test", options={"format": "wav16", "sampleRate": 44100})
    mix, stem = sf.info(r["file"]), sf.info(r["stems"]["drums"])
    assert (mix.subtype, mix.samplerate) == ("PCM_16", 44100) and Path(r["stems"]["drums"]).name == "Big_ Drums_1.wav"
    assert mix.frames == stem.frames and 1.7 < mix.duration < 1.9, "mix and stems stop together, just after the music"
    m = json.loads((Path(r["folder"]) / "manifest.json").read_text())
    assert m["bit_depth"] == "16-bit" and m["sample_rate"] == 44100 and m["stems"]["drums"]["file"] == "Big_ Drums_1.wav"
    full = handoff.render(tmp_path, doc, FakeEngine(), {}, "agent:test", options={"trim": False})
    assert sf.info(full["file"]).subtype == "PCM_24" and sf.info(full["file"]).duration == 4.0
    with pytest.raises(RostrumError, match="96000"):
        handoff.render(tmp_path, doc, FakeEngine(), {}, "agent:test", options={"format": "mp3", "sampleRate": 96000})


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
