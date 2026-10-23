"""Stems by group and the Editor preset: a stem per group and per ungrouped track, nothing twice, and the named markers
beside the files. A fake engine writes what the real one answers (every track's stem, a bus stem, `direct`)."""
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from rostrum_core import Document, Who
from rostrum_sound import KIND, handoff, presets


class GroupedEngine:
    def __init__(self, bus):
        self.bus = bus

    def request(self, do, schedule, out, stems, stemsDir):
        assert stems == "all", "the engine is asked for everything; the group choice is made after"
        rate = schedule.get("sampleRate", 48000)
        x = (0.3 * np.sin(np.linspace(0, 2000, 2 * rate)))[:, None].repeat(2, 1).astype("float32")
        files = {k: f"{stemsDir}/{k}.wav" for k in ("pad", "melody", "drums")}
        for p in [out, *files.values(), f"{stemsDir}/{self.bus}.bus.wav"]:
            sf.write(p, x, rate, subtype="FLOAT")
        return {"file": out, "stems": files, "busStems": {self.bus: f"{stemsDir}/{self.bus}.bus.wav"}, "direct": ["drums"],
                "seconds": 2.0, "lufs": -16.0, "truePeak": -1.0, "clipped": [], "tracks": []}


def test_groups_stems_and_the_editor_preset(tmp_path):
    doc = Document.new(KIND, folder=tmp_path, item="song")
    P = Who.person()
    doc.apply([{"op": "track.add", "args": {"id": t}} for t in ("pad", "melody", "drums")], P)
    doc.apply([{"op": "bus.from_tracks", "target": ["pad", "melody"], "args": {"name": "Music"}}], P)
    doc.apply([{"op": "marker.add", "args": {"name": "drop", "at": 1.5}}], P)
    doc.save()
    o = presets.expand({}, "editor")
    r = handoff.render(tmp_path, doc, GroupedEngine(doc.data["buses"][0]["id"]), {}, "agent:test", stems=o["stems"], markers_file=o["markers"],
                       master=o["master"], options={k: o[k] for k in ("format", "sampleRate", "trim")})
    folder = Path(r["folder"])
    assert sorted(p.name for p in folder.glob("*.wav")) == ["Music.wav", "drums.wav", "song_mix.wav"]
    assert sf.info(r["file"]).subtype == "FLOAT" and sf.info(r["file"]).samplerate == 48000 and sf.info(r["file"]).duration == 2.0
    data = json.loads((folder / "markers.json").read_text())
    assert {"name": "drop", "seconds": 1.5} in data["markers"]
    m = json.loads((folder / "manifest.json").read_text())
    assert m["stems_by"] == "groups" and m["markers_file"] == "markers.json"
