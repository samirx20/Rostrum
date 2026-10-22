"""A range export is that stretch of the song, at the right place: rendered by the engine itself (P29: mastered and
measured on its own, its silent end trimmed), or cut here from a whole-song render."""
import numpy as np
import pytest
import soundfile as sf
from rostrum_core import RostrumError

from rostrum_sound import deliver


def _render(tmp_path, seconds=4, rate=48000):
    mix = tmp_path / "song_mix.wav"
    ramp = np.linspace(0, 0.9, seconds * rate, dtype="float32")          # the value says where in the song a frame is
    sf.write(str(mix), np.stack([ramp, ramp], 1), rate, subtype="FLOAT")
    return {"file": str(mix), "stems": {}, "busStems": {}}


def test_range_is_cut_from_the_whole_render(tmp_path):
    opts = deliver.Options.read({"format": "wav32f", "sampleRate": 48000, "from": 1.0, "to": 2.5})
    r = deliver.deliver(tmp_path, _render(tmp_path), {}, opts, "song")
    x, _ = sf.read(r["file"], dtype="float32")
    assert abs(r["seconds"] - 1.5) < 1e-3 and r["range"] == [1.0, 2.5] and r["trimmed"] is False
    assert abs(x[0, 0] - 0.9 * 1.0 / 4) < 1e-3                           # starts where 1.0 s of the song is


def test_a_range_that_is_not_in_the_song_says_so(tmp_path):
    with pytest.raises(RostrumError):
        deliver.Options.read({"from": 3, "to": 2})
    with pytest.raises(RostrumError, match="starts after the song ends"):
        deliver.deliver(tmp_path, _render(tmp_path), {}, deliver.Options.read({"sampleRate": 48000, "from": 9, "to": 10}), "song")


def test_a_range_the_engine_rendered_is_not_cut_again_and_its_silent_end_goes(tmp_path):
    rate = 48000
    mix = tmp_path / "song_mix.wav"
    x = np.zeros((3 * rate, 2), "float32"); x[: rate, :] = 0.5                 # 1 s of sound, then 2 s of silence
    sf.write(str(mix), x, rate, subtype="FLOAT")
    r = {"file": str(mix), "stems": {}, "busStems": {}, "range": [10.0, 13.0], "seconds": 60.0}
    out = deliver.deliver(tmp_path, r, {}, deliver.Options.read({"format": "wav32f", "sampleRate": rate, "from": 10, "to": 13}), "song")
    y, _ = sf.read(out["file"], dtype="float32")
    assert y[0, 0] == 0.5 and abs(out["seconds"] - (1.0 + deliver.TAIL)) < 1e-3 and out["trimmed"] is True
    assert out["range"] == [10.0, 10.0 + out["seconds"]] and out["songSeconds"] == 60.0
