"""What agents rely on: an asked hit buried by a loud bed after it is named (buried_hit), a hit with quiet after it is
not, and the loudness note reads the brief's own tolerance and, with a hit, never says "lift the quiet parts"."""
import numpy as np
import soundfile as sf

from rostrum_sound.listen import fault_shape, hit_room

SR = 48000
BRIEF = {"brief": "One hard hit at 31.5 s, the loudest moment. After the hit: 2-3 s of near silence, then a low drone. "
                  "About -16 LUFS integrated (within 1 LU)."}


def _piece(tmp_path, bed_after):
    t = np.arange(int(45 * SR)) / SR
    y = 0.05 * np.sin(2 * np.pi * 220 * t)                            # the bed
    hit = (t >= 31.5) & (t < 33.5)
    y[hit] = 0.8 * np.sin(2 * np.pi * 110 * t[hit]) * np.exp(-(t[hit] - 31.5))
    y[(t >= 33.5) & (t < 35.5)] = 0.0
    after = t >= 35.5
    y[after] = bed_after * np.sin(2 * np.pi * 220 * t[after])
    f = tmp_path / f"p{bed_after}.wav"
    sf.write(f, np.stack([y, y], axis=1), SR)
    return str(f)


def test_loud_bed_after_hit_is_named_quiet_is_not(tmp_path):
    mo = [{"at": 31.5, "kind": "hit"}]
    loud = hit_room.faults(_piece(tmp_path, 0.6), mo, BRIEF)
    assert [f["kind"] for f in loud] == ["buried_hit"] and "bed" in loud[0]["measured"]["short"]
    assert hit_room.faults(_piece(tmp_path, 0.02), mo, BRIEF) == []


def test_loudness_reads_brief_tolerance_and_spares_the_hit():
    assert fault_shape.loudness_fault(-16.8, -16, data=BRIEF, hit=True) == []        # within the brief's 1 LU
    f = fault_shape.loudness_fault(-17.4, -16, data=BRIEF, hit=True)[0]
    assert "-17 to -15" in f["what"] and "master(loudness=-17)" in f["fix"] and "quietest parts" not in f["fix"]
    assert fault_shape.loudness_fault(-16.8, -16)                                       # no brief: 0.5 LU
