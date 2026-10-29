"""What agents rely on: a checked reply with a loudness miss opens NOT DONE, and the final export refuses it unless
`keep` explains it (synthetic numbers, no engine)."""
import shutil

import numpy as np
import pytest
import soundfile as sf
from rostrum_core import RostrumError
from rostrum_core.mcp import Reply
from rostrum_core.mcp import faults as shared

from rostrum_sound import delivered
from rostrum_sound.listen import fault_shape


def test_loudness_miss_opens_not_done_and_delivery_needs_keep(tmp_path):
    found = fault_shape.loudness_fault(-16.9, -14.0)
    assert [f["id"] for f in found] == ["loudness"]
    assert Reply("Rendered.", faults=found).to_dict()["summary"].startswith("NOT DONE: 1 fault. [loudness]")
    assert Reply("Rendered.", faults=fault_shape.loudness_fault(-14.2, -14.0)).to_dict()["summary"].startswith("DONE:")
    shared.deliver(fault_shape.loudness_fault(-16.9, -14.0), {"loudness": "a quiet documentary bed on purpose"}, "render_mix")


def _refused(tmp_path, fmt="WAV", ext="wav"):
    """render_mix's refusal with a `folder` (tools_render.deliver_checked): the render in the project's renders/ becomes
    NOT-DONE, marked and recorded; nothing is written in the delivery folder."""
    project, out = tmp_path / "project", tmp_path / "out"
    v = project / "renders" / "song" / "v001"
    v.mkdir(parents=True)
    out.mkdir()
    mix = v / f"song_mix.{ext}"
    sf.write(mix, (np.random.default_rng(1).standard_normal((4800, 2)) * 0.1).astype(np.float32), 48000, format=fmt)
    kept = delivered.refuse(mix, ["loudness"], out / mix.name, project / "renders", out)
    return project, out, mix, kept


def test_a_refused_render_copied_into_place_is_not_delivered(tmp_path):
    project, out, mix, kept = _refused(tmp_path)
    asked = out / mix.name
    assert kept.name == "song_mix.NOT-DONE.wav" and not mix.exists() and not asked.exists()
    assert "Nothing was written at" in delivered.words(asked, kept)
    shutil.copy(kept, asked)                            # the bypass round sound-vault saw: copied by hand to the asked name
    c = delivered.check(asked)
    assert not c["delivered"] and "ROSTRUM NOT DONE: loudness" in c["why"]
    assert delivered.main([str(asked)]) == 1
    stale = delivered.stale_faults(project)            # every later render_mix / look reply opens with it
    assert [f["id"] for f in stale] == ["refused_copy:song_mix.wav"] and "refused render copied into place" in stale[0]["what"]
    assert delivered.stale_faults(project, skip=[str(asked)]) == []      # a delivery to that same path replaces it
    data, rate = sf.read(kept, dtype="float32")         # the mark leaves the audio readable
    asked.unlink()
    sf.write(asked, data, rate, subtype="FLOAT")      # the same samples re-saved without the mark: the record still names them
    assert not delivered.check(asked)["delivered"]
    sf.write(asked, data * 0.5, rate, subtype="FLOAT")  # different audio: not a refused render
    assert delivered.check(asked)["delivered"] and delivered.stale_faults(project) == []


@pytest.mark.parametrize("fmt,ext", [("WAV", "wav"), ("FLAC", "flac")])
def test_the_mark_survives_a_copy_and_a_rename(tmp_path, fmt, ext):
    _, _, _, kept = _refused(tmp_path, fmt, ext)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    moved = elsewhere / f"final.{ext}"                  # no record anywhere near it: only the mark can tell
    shutil.copy(kept, moved)
    assert delivered.marked(moved) == "ROSTRUM NOT DONE: loudness"
    assert not delivered.check(moved)["delivered"]
    assert sf.info(str(moved)).frames == 4800
