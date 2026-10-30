"""An MP4 with the project's sound: asked for and failed = the export fails with nothing left (never a silent file);
the mux itself puts a sound stream under an unchanged picture."""
import subprocess
import wave
from pathlib import Path

import pytest
from rostrum_core.errors import RostrumError

from rostrum2d import settings
from rostrum2d.io import export_sound
from rostrum2d.mcp import exporting

SCENE = {"comp": {"id": "c", "props": {"width": 32, "height": 16, "fps": 10, "duration": 1.0}}}


def _tiny_mp4(path: Path):
    subprocess.run([settings.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=32x16:r=10:d=1",
                    "-c:v", "mpeg4", str(path)], check=True, timeout=60)


def _tiny_wav(path: Path, seconds=2.0, rate=48000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2), w.setsampwidth(2), w.setframerate(rate)
        w.writeframes(b"\x10\x00" * 2 * int(seconds * rate))


def test_sound_asked_and_failed_leaves_no_file(tmp_path, monkeypatch):
    import importlib
    io_export = importlib.import_module("rostrum2d.io.export")      # the module (rostrum2d.io re-exports the function)

    def fake_export(eng, fmt, target, *a, **kw):
        _tiny_mp4(Path(target))
        return {"file": str(target), "frames": 10, "fps": 10, "alpha": False, "depth": 8, "checked": {}}

    def no_mix(folder, song):
        raise RuntimeError("the sound engine is missing")

    monkeypatch.setattr(io_export, "export", fake_export)
    monkeypatch.setattr(export_sound, "mix", no_mix)
    monkeypatch.setattr(exporting.project_sound, "check_before_export", lambda *a: None)   # no song file here: the mix itself fails
    s = exporting.settings("t", "mp4", 1.0, sound="snd_main")
    with pytest.raises(RostrumError, match="sound engine is missing"):
        exporting.run("t", SCENE, "mp4", s, folder=tmp_path, out=tmp_path / "a.mp4", engine_factory=lambda: _NoEngine())
    assert list(tmp_path.iterdir()) == []


def test_sound_only_on_mp4():
    with pytest.raises(RostrumError, match="carries no sound"):
        exporting.settings("t", "gif", 1.0, sound="snd_main")


def test_attach_puts_the_mix_under_the_picture(tmp_path):
    video, wav = tmp_path / "v.mp4", tmp_path / "m.wav"
    _tiny_mp4(video), _tiny_wav(wav)
    assert not export_sound.has_sound(video)
    export_sound.attach(video, tmp_path, "snd_main", 0.5, 1.0, wav=wav)
    assert export_sound.has_sound(video)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["m.wav", "v.mp4"]


class _NoEngine:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def load(self, scene):
        pass


def test_an_empty_song_exports_picture_only_and_says_so(tmp_path):
    """Sound's fresh empty song shares the project: an export with sound used to fail on it after drawing every frame.
    It is decided before frame 1: no sound under the picture, and the reply says why (no gate: the export happens)."""
    from rostrum_core import Document, Who
    from rostrum_core.storage import save
    from rostrum_sound import KIND as SOUND
    from rostrum_sound.doc import markers as sound_markers
    from rostrum2d import project_sound
    (tmp_path / "docs").mkdir()
    with sound_markers.project(tmp_path):
        save(Document.new(SOUND, tmp_path, "song"))
    assert project_sound.song(tmp_path) is not None and project_sound.empty(tmp_path, "song")
    assert project_sound.for_export(tmp_path, "", "mp4", None) is None
    assert project_sound.for_export(tmp_path, "", "mp4", True) is None        # asked: still picture-only, never refused
    assert 'the song "song" has nothing in it yet' in exporting.next_steps("look", False, tmp_path)
