"""The balls' light (SPEC §6.1): one small sky picture, made here once and kept in the balls' cache folder, so every
ball is lit the same way. Storm lights a scene only through a dome, so the set-up is a lat-long picture: a clear key
softbox up on the left, a soft fill low on the right, two strips behind for a rim, over a dim grey sweep. Raise
`LOOK` (and ball_key's SETUP_VERSION) when it changes.

    path = studio_picture(folder)     # <folder>/ball-studio-<LOOK>.hdr (Radiance RGBE, written once)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

LOOK = 1
W, H = 256, 128
# (centre azimuth°, centre elevation°, half width°, half height°, radiance): azimuth 0 faces the camera, + to the left
LIGHTS = [
    (45, 40, 28, 22, 14.0),      # key: big, up and to the left
    (-75, 0, 40, 35, 2.4),        # fill: soft, right, level
    (-140, 15, 8, 40, 8.0),      # rim: tall strip behind right
    (140, 15, 8, 40, 5.0),      # rim: tall strip behind left
]


def _smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def radiance() -> np.ndarray:
    """The picture as float RGB, H × W × 3."""
    az = (np.arange(W) + 0.5) / W * 360 - 180
    el = 90 - (np.arange(H) + 0.5) / H * 180
    az, el = np.meshgrid(az, el)
    v = np.where(el > 0, 0.15 + 0.06 * el / 90, 0.09 + 0.05 * _smooth(-30, 0, el))      # grey sweep, darker floor
    for caz, cel, haz, hel, power in LIGHTS:
        d = np.abs((az - caz + 540) % 360 - 180)
        v = v + power * (1 - _smooth(haz * 0.6, haz, d)) * (1 - _smooth(hel * 0.6, hel, np.abs(el - cel)))
    return np.repeat(v[..., None], 3, axis=2).astype(np.float32)


def _rgbe(rgb: np.ndarray) -> bytes:
    m = rgb.max(axis=2)
    mant, exp = np.frexp(np.maximum(m, 1e-32))
    scale = np.where(m > 1e-32, mant * 256.0 / np.maximum(m, 1e-32), 0)
    out = np.zeros((*m.shape, 4), np.uint8)
    out[..., :3] = np.clip(rgb * scale[..., None], 0, 255).astype(np.uint8)
    out[..., 3] = np.where(m > 1e-32, exp + 128, 0).astype(np.uint8)
    return out.tobytes()


def studio_picture(folder: Path) -> str:
    """The sky picture's path (written the first time, atomically)."""
    file = folder / f"ball-studio-{LOOK}.hdr"
    if not file.is_file():
        folder.mkdir(parents=True, exist_ok=True)
        tmp = file.with_suffix(".partial")
        tmp.write_bytes(f"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y {H} +X {W}\n".encode() + _rgbe(radiance()))
        tmp.replace(file)
    return str(file)
