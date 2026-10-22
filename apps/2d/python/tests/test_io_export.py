"""Export read-back must fail loudly on a wrong frame count and on missing alpha (tiny files made on the fly)."""
import subprocess

import numpy as np
import pytest
from PIL import Image

from rostrum2d import settings
from rostrum2d.io import formats, readback


def _has_ffmpeg() -> bool:
    try:
        return bool(settings.ffmpeg())
    except RuntimeError:
        return False


pytestmark = pytest.mark.skipif(not _has_ffmpeg(), reason="Rostrum2D's FFmpeg missing (apps/2d/ffmpeg)")
W, H = 32, 16


def _frames(n, alpha):
    a = np.zeros((n, H, W, 4), np.uint8)
    a[..., :3] = 200
    a[..., 3] = 255
    if alpha:
        a[:, :, : W // 2, 3] = 0
    return a.tobytes()


def _encode(fmt, out, n, alpha):
    spec = formats.get(fmt).build(str(out), W, H, 10, 8, 0, 0)
    subprocess.run([spec["program"], *spec["args"]], input=_frames(n, alpha), check=True, capture_output=True)


def test_wrong_frame_count_fails(tmp_path):
    _encode("webm", tmp_path / "a.webm", 4, True)
    with pytest.raises(readback.ExportError, match="expected 6 frames"):
        readback.check("webm", tmp_path / "a.webm", 6, W, H, True)


def test_missing_alpha_fails(tmp_path):
    _encode("webm", tmp_path / "a.webm", 4, False)           # alpha format, but every pixel opaque
    with pytest.raises(readback.ExportError, match="alpha"):
        readback.check("webm", tmp_path / "a.webm", 4, W, H, True)
    _encode("webm", tmp_path / "b.webm", 4, True)
    assert readback.check("webm", tmp_path / "b.webm", 4, W, H, True)["min_alpha"] == 0


def test_png_bit_depth_and_alpha(tmp_path):
    a = np.zeros((H, W, 4), np.uint8)
    Image.fromarray(a, "RGBA").save(tmp_path / "f_0000.png")
    with pytest.raises(readback.ExportError, match="asked 16"):
        readback.check("png", tmp_path / "f_{frame}.png", 1, W, H, True, 16)
