"""What agents rely on: the moment the brief asked for says so and is not kept on a first render or without a measured
number; a kick left in a drop's gap is heard on the drum tracks; ring_past_length is bounded (synthetic, no engine)."""
import numpy as np
import pytest
import soundfile as sf
from rostrum_core import RostrumError

from rostrum_sound import deliver
from rostrum_sound.listen import drop_gap, fault_shape
from rostrum_sound.mcp import asked_keep

SR = 48000


def shaped():
    raw = [{"kind": "weak_hit", "at_s": 31.5, "words": "weak hit at 31.50 s: 0.8x a normal note; fix: rest the bed"},
           {"kind": "held_tone", "at_s": 0.0, "words": "one harmony held; fix: move the bass"}]
    found = [{"id": "weak_hit@31.5", "what": "weak hit", "when": "31.50 s", "fix": "rest the bed"},
             {"id": "held_tone", "what": "held", "when": None, "fix": "move the bass"}]
    asked_keep.mark(raw, found, [{"at": 31.5, "kind": "hit"}, {"kind": "tempo", "bpm": 70}])
    return found


def test_the_briefs_own_moment_is_harder_to_keep():
    found = shaped()
    assert found[0]["asked"] and found[0]["what"].startswith("the moment the brief asked for (hit at 31.50 s)")
    assert not found[1].get("asked")
    keep = {"weak_hit@31.5": "it is 10 dB over the bed", "held_tone": "the drone is the scene"}
    first = asked_keep.screen(found, keep, seen_before=set())            # first render: no fix tried yet
    assert first == {"held_tone": "the drone is the scene"} and "keep refused" in found[0]["fix"]
    found = shaped()
    assert "weak_hit@31.5" not in asked_keep.screen(found, {"weak_hit@31.5": "loud enough on purpose"}, {"weak_hit@31.5"})
    found = shaped()
    assert asked_keep.screen(found, keep, {"weak_hit@31.5"}) == keep    # tried once, a measured number: kept


def test_a_kick_in_the_gap_is_heard_on_the_drum_track(tmp_path):
    t = np.arange(int(30 * SR)) / SR
    kicks = sum(np.exp(-np.clip(t - k, 0, None) * 30) * (t >= k) * np.sin(2 * np.pi * 55 * t) for k in np.arange(20, 30, 0.5) if not 24 <= k < 26)
    clean, leaky = tmp_path / "clean.wav", tmp_path / "leaky.wav"
    sf.write(clean, np.stack([kicks, kicks], 1).astype(np.float32), SR)
    leak = kicks + 0.3 * np.exp(-np.clip(t - 24.5, 0, None) * 30) * (t >= 24.5) * np.sin(2 * np.pi * 55 * t)
    sf.write(leaky, np.stack([leak, leak], 1).astype(np.float32), SR)
    mix = np.zeros(int(30 * SR))
    assert drop_gap.faults(mix, SR, 24.0, 26.0, [str(clean)]) == []
    f = drop_gap.faults(mix, SR, 24.0, 26.0, [str(leaky)])
    assert f and f[0]["measured"]["on"] == "tracks" and "kick included" in drop_gap.words(f[0])


def test_peaks_and_ring_past_length():
    assert [f["id"] for f in fault_shape.peak_faults((-0.4, -1), 3)] == ["true_peak", "clipped"]
    assert fault_shape.peak_faults((-1.2, -1), 0) == []
    assert "maxLimit to 6.1" in fault_shape.loudness_fault(-17.4, -16, push=6.1)[0]["fix"]
    assert deliver.ring_allowed(None) == 0 and deliver.ring_allowed(True) == deliver.RING_S and deliver.ring_allowed(1.5) == 1.5
    with pytest.raises(RostrumError):
        deliver.ring_allowed(10)
