"""What agents rely on: render_audition's stretch asks the engine for only that stretch of the song as written now, the
same stretch of the same song again is the cached file (no render), a changed song is heard anew, and the picture is
drawn without a plotting library. A stand-in engine writes the file."""
from pathlib import Path

import numpy as np
import soundfile as sf

from rostrum_sound import hear
from rostrum_sound.builder import Song


class Engine:
    def __init__(self):
        self.asked = []

    def request(self, op, **kw):
        self.asked.append(kw)
        out = Path(kw["out"])
        sf.write(out, np.zeros((4800, 2), np.float32) + 0.1, 48000)
        out.with_suffix(".levels.json").write_text("{}", encoding="utf-8")
        return {"range": [kw["from"], kw["to"]], "lufs": -14.0, "truePeak": -1.5, "series": {"shortTerm": [-14.0] * 10}}


def song(vel=0.8):
    s = Song()
    s.set(tempo=120)
    s.track("piano", builtIn="piano").note(pitch="C4", at=0, dur=1, vel=vel)
    return s.tree()


def test_a_stretch_is_rendered_once_and_then_found(tmp_path):
    eng = Engine()
    a = hear.hear(eng, song(), 1.0, 3.0, out_dir=tmp_path)
    assert (eng.asked[0]["from"], eng.asked[0]["to"], eng.asked[0]["stems"]) == (1.0, 3.0, [])
    assert not a["cached"] and a["from_s"] == 1.0 and a["to_s"] == 3.0
    b = hear.hear(eng, song(), 1.0, 3.0, out_dir=tmp_path)
    assert b["cached"] and b["file"] == a["file"] and len(eng.asked) == 1
    c = hear.hear(eng, song(vel=0.5), 1.0, 3.0, out_dir=tmp_path)
    assert not c["cached"] and c["file"] != a["file"]
    png = hear.picture(str(tmp_path / "a.png"), a["file"], a, "song")
    assert Path(png).stat().st_size > 0


def test_at_around_is_a_window_each_side():
    assert hear.window(10.0, None, 2.0) == (8.0, 12.0)
    assert hear.window(1.0, None, 2.0) == (0.0, 3.0)
    assert hear.window(5.0, None, None) == (5.0, 9.0)
