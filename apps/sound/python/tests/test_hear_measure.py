"""What agents that cannot hear rely on: a heard stretch comes back as numbers in song seconds — the mix's hits and the
loudest, each part's level and starts (also when the same stretch is found in the cache), loudness per row. A stand-in
engine writes the stretch: two clicks on silence, the second louder."""
from pathlib import Path

import numpy as np
import soundfile as sf

from rostrum_sound import hear, hear_measure
from rostrum_sound.builder import Song

SR = 48000


class Engine:
    def request(self, op, **kw):
        y = np.zeros((SR * 2, 2), np.float32)
        for at, amp in ((0.5, 0.2), (1.5, 0.8)):
            i = int(at * SR)
            y[i:i + 480] = amp
        out = Path(kw["out"])
        sf.write(out, y, SR)
        out.with_suffix(".levels.json").write_text("{}", encoding="utf-8")
        return {"range": [kw["from"], kw["to"]], "lufs": -20.0, "truePeak": -2.0,
                "tracks": [{"id": "drums", "peak": 0.8, "rms": 0.1, "lufs": -21.0, "span": [0.0, 1.51],
                            "onsets": [0.0, 0.5, 1.5], "bands": [-40, -30, -20, -25, -35]}]}


def test_the_stretch_reads_as_numbers_in_song_seconds_also_from_the_cache(tmp_path):
    s = Song()
    s.set(tempo=120)
    s.track("drums", instrument="kit", kit="drums").hit(drum="kick", at=10.5, vel=0.8)
    for cached in (False, True):
        r = hear.hear(Engine(), s.tree(), 10.0, 12.0, out_dir=tmp_path)
        assert r["cached"] is cached
        m = hear_measure.measure(r["file"], r)
        assert [h["t"] for h in m["hits"]] == [10.5, 11.5] and m["strongest_hit"]["t"] == 11.5 and m["loudest_row"]["t"] == 11.5
        part = m["parts"][0]
        assert part["id"] == "drums" and part["onsets"] == [10.5, 11.5] and (part["from_s"], part["to_s"]) == (10.0, 11.51)
        assert part["lufs"] == -21.0 and part["bands"]["mid"] == -25
    assert [row["t"] for row in m["loudness"]] == [10.0, 10.5, 11.0, 11.5]
    assert m["loudness"][3]["lufs"] > m["loudness"][1]["lufs"] > m["loudness"][0]["lufs"] == hear_measure.FLOOR
    said = hear_measure.lines(m)
    assert "Mix hits (2" in said and "strongest hit 11.5@" in said and "loudest row 11.5s" in said and "Part drums" in said
