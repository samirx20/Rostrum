"""What agents rely on: a delivery (render_mix `folder`) waits while a fault is open and unexplained; a kept fault needs
a real reason; the file's own faults (past its length, off its loudness target) are named; ring_past_length is bounded."""
import pytest
from rostrum_core import RostrumError

from rostrum_sound import deliver
from rostrum_sound.mcp import deliver_hold as H

MASTER = {"normalize": True, "loudness": -16, "truePeak": -1}


def r(seconds=40.0, lufs=-16.1, tp=-1.2, clipped=0):
    return {"seconds": seconds, "lufs": lufs, "truePeak": tp, "clipped": clipped}


def test_the_files_own_faults():
    assert H.delivery_faults(r(), MASTER, 40.0, 0.0) == []
    kinds = [f["kind"] for f in H.delivery_faults(r(seconds=42.3, lufs=-17.4, tp=-0.5, clipped=3), MASTER, 40.0, 2.0)]
    assert kinds == ["runs_long", "off_loudness", "peak_over", "clipped"]
    assert H.delivery_faults(r(seconds=41.9), MASTER, 40.0, 2.0) == []          # inside the ring allowed
    assert H.delivery_faults(r(lufs=-20), {"normalize": False}, None, 0.0) == []  # no target, no length: nothing to hold to


def test_open_faults_hold_until_each_is_kept_with_a_reason():
    found = [{"kind": "weak_hit", "at_s": 31.5, "words": "weak hit"}, {"kind": "held_tone", "at_s": 0.0, "words": "held"}]
    still, kept = H.decide(found, [])
    assert [f["kind"] for f in still] == ["weak_hit", "held_tone"] and kept == []
    words = H.held_words(still, "C:/out")
    assert words.startswith("NOT DELIVERED") and '"fault": "weak_hit"' in words
    keep = H.read_keep([{"fault": "held_tone", "why": "the drone is the scene's held breath"}])
    still, kept = H.decide(found, keep)
    assert [f["kind"] for f in still] == ["weak_hit"] and kept[0]["fault"] == "held_tone"
    keep = H.read_keep([{"fault": "weak_hit", "at": 20.0, "why": "a different moment entirely"}])
    assert [f["kind"] for f in H.decide(found, keep)[0]] == ["weak_hit", "held_tone"]   # another time does not keep it
    with pytest.raises(RostrumError):
        H.read_keep([{"fault": "weak_hit", "why": "on purpose"}])                     # not a reason


def test_ring_past_length_is_bounded():
    assert deliver.ring_allowed(None) == 0 and deliver.ring_allowed(True) == deliver.RING_S and deliver.ring_allowed(1.5) == 1.5
    with pytest.raises(RostrumError):
        deliver.ring_allowed(10)
