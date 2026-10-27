"""What agents rely on (critic r12): inspect_markers lists the song's own markers (it said "0 markers" while the song
had five), the ending check gives an audible end, and look_sound's loudness is measured per section."""
import numpy as np
import soundfile as sf
from rostrum_core import Document, Who

from rostrum_sound import KIND, listen
from rostrum_sound.listen.ending import ending
from rostrum_sound.mcp.app import make_app
from rostrum_sound.mcp.server import make_runtime

AGENT = Who.agent("tester")
SR = 48000


def test_inspect_markers_lists_the_songs_own_markers(tmp_path, monkeypatch):
    (tmp_path / "engine.exe").write_bytes(b"")              # never started: no render here
    monkeypatch.setenv("ROSTRUM_SOUND_ENGINE", str(tmp_path / "engine.exe"))
    d = Document.new(KIND, folder=str(tmp_path), item="cue")
    d.apply([{"op": "marker.add", "args": {"name": "sun", "at": 33.9}},
             {"op": "marker.add", "args": {"name": "hit", "at": {"beat": 8}}}], AGENT)
    d.save()
    app = make_app(str(tmp_path), ["cue"])
    rt = make_runtime(app)
    reply, _ = rt.call("inspect_markers", {}, AGENT)
    assert reply["ok"], reply
    got = {m["name"]: m["at"] for m in reply["data"]["song_markers"]}
    assert got == {"sun": 33.9, "hit": 4.0} and "2 song markers" in reply["summary"]
    one, _ = rt.call("inspect_markers", {"name": "SUN"}, AGENT)
    assert one["data"]["at"] == 33.9


def _tone(seconds, db):
    t = np.arange(int(seconds * SR)) / SR
    return (10 ** (db / 20) * np.sqrt(2) * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def test_the_audible_end_is_where_the_sound_falls_under_minus_60_for_good():
    y = np.concatenate([_tone(2.0, -20), _tone(1.0, -50), _tone(1.0, -80)])      # loud, a quiet tail, then inaudible
    e = ending(np.stack([y, y], axis=1), SR)
    assert abs(e["audible_end_s"] - 3.0) <= 0.05 and "Audible end 3.00 s" in e["words"]


def test_loudness_by_section_measures_each_stretch(tmp_path):
    wav = tmp_path / "mix.wav"
    sf.write(wav, np.concatenate([_tone(3.0, -30), _tone(3.0, -15)]), SR)
    quiet, loud = listen.by_section(str(wav), [("verse", 0.0, 3.0), ("build", 3.0, 6.0), ("past the end", 7.0, 9.0)])
    assert quiet["name"] == "verse" and loud["integrated_lufs"] - quiet["integrated_lufs"] > 14
