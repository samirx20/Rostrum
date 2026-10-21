"""The video frame pick (the one rule the engine's `video_picture` repeats) and loud failures."""
import pytest

from rostrum2d import video


def test_the_frame_for_a_time():
    pick = lambda n, **k: video.pick(n, **{"start": 0, "fps": 30, "speed": 1, "offset": 0, "count": 60, "loop": False, **k})
    assert pick(30) == 30
    assert pick(10, start=0.2, speed=2, offset=0.5) == 23       # floor((10 − 6)·2) + round(0.5·30)
    assert pick(70) == 59 and pick(70, loop=True) == 10          # held at the last frame, or wrapped
    assert pick(0, start=1) == 0 and pick(0, start=1, loop=True) == 30    # before the layer starts: held / wrapped


def test_a_missing_file_fails_loudly():
    with pytest.raises(FileNotFoundError, match="clip.src"):
        video.frames({"id": "clip", "src": "nowhere.mp4", "w": 64, "h": 64}, 30)
