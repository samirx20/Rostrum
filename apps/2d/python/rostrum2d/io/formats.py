"""The export formats: one table. Each entry builds the encoder command the engine pipes its frames into.

Licences: prores_ks is FFmpeg's own native encoder and libvpx is BSD, so both are in an LGPL FFmpeg build.
MP4 (H.264) is written by the engine through the operating system's own encoder (Windows Media Foundation; the GPU's
encoder when there is one), never libx264 (GPL) and no FFmpeg. PNG and EXR are written by the engine itself too; a GIF by gif_encode.py.
EXR is the hand-off to the Editor (shared/HANDOFFS.md § 2): `<stem>.<frame>.exr` from 1001, half float ACEScg,
premultiplied, the beauty as part `rgba`.
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, NamedTuple

from .. import settings
from ..engine import find_exe

PIX = {8: "rgba", 16: "rgba64le"}          # the raw frames the engine pipes: straight alpha


@dataclass(frozen=True)
class Format:
    ext: str
    alpha: bool                              # can carry transparency
    depths: tuple[int, ...]                  # bits per channel it takes; the first is the default
    build: Callable[[str, int, int, int, int, int, "Rate"], dict]   # (out, w, h, fps, depth, first_frame, rate) -> encoder
    video: bool = True                       # one file; False = one file per frame (out holds {frame})
    first: int = 0                           # a sequence's number for the document's first frame
    sep: str = "_"                           # between a sequence's stem and its frame number
    qualities: tuple[str, ...] = ()          # the plain quality choices it takes (QUALITY); none = no bitrate to set


# The view a 2D picture enters linear light through (HANDOFFS § 4). One project-wide setting, still Sam's DECISION
# there; until it reaches the 2D document every hand-off uses the contract's default.
HANDOFF_VIEW = "neutral"

class Rate(NamedTuple):
    """How an MP4 spends its bits: `quality` (the encoder's constant quality, 1-100) gives each frame what its picture
    needs, and `kbps` is then only the file's nominal rate; with no quality, `kbps` is the exact (average) bitrate."""
    kbps: int
    quality: int | None = None


# MP4 quality: the encoder's constant quality (E15, measured on Night Bloom against lossless frames: flat motion
# graphics need a few Mbit/s, a busy shot gets more). Best ≈ 4.7× smaller than the old fixed 0.96 bits per pixel at
# VMAF 98.5 vs 98.8, SSIM 0.991 vs 0.994 (1 VMAF step people notice ≈ 6). An exact bitrate (Mbit/s, MAX_MBIT at
# most) replaces the choice.
QUALITY = {"standard": 85, "high": 95, "best": 100}
DEFAULT_QUALITY = "high"
NOMINAL_BPP = 0.24                           # the nominal rate written in the file with a quality: bits per pixel per frame
MAX_MBIT = 160                               # H.264 High at level 5.1 carries 300; GPU encoders stay well under it


def _ffmpeg(depth: int, w: int, h: int, fps: int, codec_args: list[str], out: str) -> dict:
    return {"program": settings.ffmpeg(), "args": [
        "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", PIX[depth], "-s", f"{w}x{h}",
        "-r", str(fps), "-i", "-", *codec_args, out]}


def rate(f: Format, w: int, h: int, fps: int, quality: str | None = None, bitrate: float | None = None) -> Rate:
    """How `f` is encoded: an exact `bitrate` (Mbit/s) if given, else the quality's; Rate(0) for a format that takes
    none."""
    if not f.qualities:
        if quality is not None or bitrate is not None:
            raise ValueError("this format takes no quality or bitrate")
        return Rate(0)
    if bitrate is not None:
        if not 0 < bitrate <= MAX_MBIT:
            raise ValueError(f"bitrate must be above 0 and at most {MAX_MBIT} Mbit/s; got {bitrate:g}")
        return Rate(round(bitrate * 1000))
    q = DEFAULT_QUALITY if quality is None else quality
    if q not in f.qualities:
        raise ValueError(f"quality '{q}' is not one of {', '.join(f.qualities)}")
    return Rate(min(round(NOMINAL_BPP * w * h * fps / 1000), MAX_MBIT * 1000), QUALITY[q])


def _mp4(out, w, h, fps, depth, first, rate):
    exe = str(find_exe())
    _can_write_mp4(exe)
    q = [] if rate.quality is None else [str(rate.quality)]
    return {"program": exe, "args": ["encode-mp4", out, str(w), str(h), str(fps), str(rate.kbps), *q]}


def _can_write_mp4(exe: str):
    """The engine's own check, before any frame is rendered: on a Windows without Media Foundation (N editions) its
    plain reason is raised as it is."""
    r = subprocess.run([exe, "encode-mp4", "--check"], capture_output=True, text=True, timeout=60,
                       creationflags=settings.NO_WINDOW)
    if r.returncode:
        said = r.stderr.strip().removeprefix("encode-mp4: ")
        raise RuntimeError(said or f"{exe} encode-mp4 --check failed (exit {r.returncode}) and said nothing")


def _prores(out, w, h, fps, depth, first, rate):   # prores_ks: native FFmpeg encoder, LGPL build
    return _ffmpeg(depth, w, h, fps, [
        "-c:v", "prores_ks", "-profile:v", "4", "-pix_fmt", "yuva444p10le", "-alpha_bits", "16", "-vendor", "apl0",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"], out)


def _webm(out, w, h, fps, depth, first, rate):     # libvpx-vp9: BSD, LGPL build
    return _ffmpeg(depth, w, h, fps, [
        "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0", "-b:v", "0", "-crf", "24", "-row-mt", "1",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"], out)


# GIF: a size and a frame rate to choose (a full-HD GIF at the scene's rate is tens of MB); how big the file will be is
# measured before it is made (gif_size.py). The picture is encoded by gif_encode.py (one palette, ordered dither), not the engine's encode-gif.
GIF_SIZES = {"full": "Full size", "half": "Half size", "480": "480 px wide"}
GIF_RATES = {"15": "15 frames a second", "scene": "The scene's rate"}
GIF_DEFAULTS = {"size": "half", "rate": "15"}


def gif_shape(w: int, h: int, fps: float, frames: int, size: str = "half", rate: str = "15") -> tuple[int, int, float, int]:
    """(width, height, fps, frames) of the GIF for a scene of w × h at fps with `frames` frames: the chosen size (never
    larger than the scene) and rate (never faster than the scene)."""
    if size not in GIF_SIZES or rate not in GIF_RATES:
        raise ValueError(f"GIF size is one of {', '.join(GIF_SIZES)} and rate one of {', '.join(GIF_RATES)}; got {size}, {rate}")
    ow = {"full": w, "half": max(1, round(w / 2)), "480": min(w, 480)}[size]
    oh = max(1, round(h * ow / w))
    ofps = min(fps, 15.0) if rate == "15" else fps
    return ow, oh, ofps, max(1, round(frames * ofps / fps))


def gif_encode(out, w, h, fps, size="half", rate="15") -> dict:
    """The encoder command for a GIF of a scene w × h at fps, at the chosen size and rate."""
    ow, oh, ofps, _ = gif_shape(w, h, fps, 1, size, rate)
    return {"program": sys.executable, "args": ["-I", str(Path(__file__).with_name("gif_encode.py")), str(out), str(w), str(h),
                                                 f"{fps:g}", str(ow), str(oh), f"{ofps:g}"]}


def _gif(out, w, h, fps, depth, first, rate):       # the table's own: full size at the scene's rate (export() passes the chosen ones)
    return gif_encode(out, w, h, fps, "full", "scene")


def _png(out, w, h, fps, depth, first, rate):
    return {"program": str(find_exe()), "args": ["encode-png", out, str(w), str(h), str(depth), str(first)]}


def _exr(out, w, h, fps, depth, first, rate):
    return {"program": str(find_exe()), "args": ["encode-exr", out, str(w), str(h), str(first), str(fps), HANDOFF_VIEW]}


FORMATS: dict[str, Format] = {
    "mp4": Format(".mp4", False, (8,), _mp4, qualities=tuple(QUALITY)),
    "prores4444": Format(".mov", True, (16,), _prores),
    "webm": Format(".webm", True, (8,), _webm),
    "gif": Format(".gif", True, (8,), _gif),
    "png": Format(".png", True, (8, 16), _png, video=False),
    "exr": Format(".exr", True, (16,), _exr, video=False, first=1001, sep="."),
}


def pattern(f: Format, out) -> str:
    """Where a sequence's files go: `out` holding {frame} as it is, else `<stem><sep>{frame}<ext>` beside it."""
    s = str(out)
    if "{frame}" in s:
        return s
    stem = str(Path(s).with_suffix("")) if s.lower().endswith(f.ext) else s
    return f"{stem}{f.sep}{{frame}}{f.ext}"


def get(name: str) -> Format:
    if name not in FORMATS:
        raise ValueError(f"unknown export format '{name}'; choose one of {', '.join(FORMATS)}")
    return FORMATS[name]
