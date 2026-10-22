"""A range export is that stretch of the song (the engine renders it whole, deliver cuts it), at the right place."""
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
