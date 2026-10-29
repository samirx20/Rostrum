"""Export read-back must fail loudly on a wrong frame count and on alpha the file can't carry (tiny files made on the fly)."""
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


def test_mp4_counted_without_decoding_still_fails_loudly(tmp_path):
    # An MP4 is read back by its packets, not decoded (readback._probe): a short or wrong-sized file must still fail.
    out = tmp_path / "a.mp4"
    subprocess.run([settings.ffmpeg(), "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", "10",
                    "-i", "-", "-c:v", "mpeg4", str(out)], input=_frames(4, False), check=True, capture_output=True)
    assert readback.check("mp4", out, 4, W, H, False)["frames"] == 4
    with pytest.raises(readback.ExportError, match="expected 6 frames"):
        readback.check("mp4", out, 6, W, H, False)
    with pytest.raises(readback.ExportError, match="expected 64x16"):
        readback.check("mp4", out, 4, 64, H, False)


def test_alpha_is_the_files_channel_not_its_pixels(tmp_path):
    # S27 H2: a solid background is opaque everywhere; with transparency kept (the default) that file is right.
    for fmt in ("webm", "gif"):
        _encode(fmt, tmp_path / f"opaque.{fmt}", 4, False)
        assert readback.check(fmt, tmp_path / f"opaque.{fmt}", 4, W, H, True)["min_alpha"] == 255
    _encode("webm", tmp_path / "b.webm", 4, True)
    assert readback.check("webm", tmp_path / "b.webm", 4, W, H, True)["min_alpha"] == 0
    with pytest.raises(readback.ExportError, match="transparent pixels"):     # asked without alpha, yet see-through
        readback.check("webm", tmp_path / "b.webm", 4, W, H, False)
    Image.new("RGB", (W, H)).save(tmp_path / "rgb_0000.png")                  # no alpha channel at all
    with pytest.raises(readback.ExportError, match="no alpha channel"):
        readback.check("png", tmp_path / "rgb_{frame}.png", 1, W, H, True)


def test_png_bit_depth_and_alpha(tmp_path):
    a = np.zeros((H, W, 4), np.uint8)
    Image.fromarray(a, "RGBA").save(tmp_path / "f_0000.png")
    with pytest.raises(readback.ExportError, match="asked 16"):
        readback.check("png", tmp_path / "f_{frame}.png", 1, W, H, True, 16)
