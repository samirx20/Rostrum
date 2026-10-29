"""What agents rely on: a checked reply with a loudness miss opens NOT DONE, and the final export refuses it unless
`keep` explains it (synthetic numbers, no engine)."""
import numpy as np
import pytest
import soundfile as sf
from rostrum_core import RostrumError
from rostrum_core.mcp import Reply
from rostrum_core.mcp import faults as shared

from rostrum_sound.listen import fault_shape


def test_loudness_miss_opens_not_done_and_delivery_needs_keep(tmp_path):
    found = fault_shape.loudness_fault(-16.9, -14.0)
    assert [f["id"] for f in found] == ["loudness"]
    assert Reply("Rendered.", faults=found).to_dict()["summary"].startswith("NOT DONE: 1 fault. [loudness]")
    assert Reply("Rendered.", faults=fault_shape.loudness_fault(-14.2, -14.0)).to_dict()["summary"].startswith("DONE:")
    wav = tmp_path / "mix.wav"
    sf.write(wav, np.zeros((100, 2), dtype=np.float32), 48000)
    with pytest.raises(RostrumError):
        shared.deliver(found, None, "render_mix", wav)
    assert (tmp_path / "mix.NOT-DONE.wav").is_file() and not wav.exists()
    (tmp_path / "mix.NOT-DONE.wav").rename(wav)
    found = fault_shape.loudness_fault(-16.9, -14.0)
    shared.deliver(found, {"loudness": "a quiet documentary bed on purpose"}, "render_mix", wav)
    assert wav.is_file()
