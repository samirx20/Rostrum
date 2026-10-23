"""A GIF is as long as the scene whatever its frame rate, and the size and rate chosen are what comes out (a GIF is for chats:
its weight is the point), and nothing ever grows past the scene."""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from rostrum2d.io import formats, gif_encode


def test_shape_never_exceeds_the_scene():
    assert formats.gif_shape(1920, 1080, 30, 120) == (960, 540, 15.0, 60)
    assert formats.gif_shape(1920, 1080, 30, 120, "480", "scene") == (480, 270, 30, 120)
    assert formats.gif_shape(320, 180, 10, 20, "480", "15") == (320, 180, 10, 20)       # never larger or faster than the scene
    with pytest.raises(ValueError, match="size"):
        formats.gif_shape(1920, 1080, 30, 120, "huge")


def test_kept_frames_last_the_whole_scene():
    keep = [i for i in range(25) if gif_encode.kept_at(i, 25, 15)]
    assert keep[0] == 0 and len(keep) == 15
    assert sum(gif_encode.delays(keep, 25, 25)) == 100                                    # 1 s in hundredths


def test_encoder_writes_the_chosen_size_rate_and_transparency(tmp_path):
    w, h, n = 64, 32, 10
    frames = []
    for i in range(n):
        a = np.zeros((h, w, 4), np.uint8)
        a[8:24, 4 + 4 * i:20 + 4 * i] = (255, 100, 50, 255)
        frames.append(a.tobytes())
    out = tmp_path / "a.gif"
    cmd = formats.gif_encode(out, w, h, 10, "half", "15")
    r = subprocess.run([cmd["program"], *cmd["args"]], input=b"".join(frames), capture_output=True)
    assert r.returncode == 0, r.stderr.decode()
    with Image.open(out) as im:
        assert im.size == (32, 16) and im.n_frames <= n
        total = 0
        for i in range(im.n_frames):
            im.seek(i)
            total += im.info["duration"]
        assert total == 1000                                                              # the scene's second
        assert np.asarray(im.convert("RGBA"))[0, 0, 3] == 0                              # see-through stays see-through
