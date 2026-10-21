"""The export formats: one table. Each entry builds the encoder command the engine pipes its frames into.

Licences: prores_ks is FFmpeg's own native encoder and libvpx is BSD, so both are in an LGPL FFmpeg build.
H.264 through libx264 is GPL: the shipped app must use the OS / GPU encoder for mp4 instead (the dev build here
uses the system ffmpeg). GIF and PNG are written by the engine itself (no FFmpeg).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..engine import find_exe, h264

PIX = {8: "rgba", 16: "rgba64le"}          # the raw frames the engine pipes: straight alpha


@dataclass(frozen=True)
class Format:
    ext: str
    alpha: bool                              # can carry transparency
    depths: tuple[int, ...]                  # bits per channel it takes; the first is the default
    build: Callable[[str, int, int, int, int, int], dict]   # (out, w, h, fps, depth, first_frame) -> encoder
    video: bool = True                       # one file; False = one file per frame (out holds {frame})


def _ffmpeg(depth: int, w: int, h: int, fps: int, codec_args: list[str], out: str) -> dict:
    return {"program": "ffmpeg", "args": [
        "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", PIX[depth], "-s", f"{w}x{h}",
        "-r", str(fps), "-i", "-", *codec_args, out]}


def _mp4(out, w, h, fps, depth, first):
    return h264(Path(out), w, h, fps)


def _prores(out, w, h, fps, depth, first):   # prores_ks: native FFmpeg encoder, LGPL build
    return _ffmpeg(depth, w, h, fps, [
        "-c:v", "prores_ks", "-profile:v", "4", "-pix_fmt", "yuva444p10le", "-alpha_bits", "16", "-vendor", "apl0",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"], out)


def _webm(out, w, h, fps, depth, first):     # libvpx-vp9: BSD, LGPL build
    return _ffmpeg(depth, w, h, fps, [
        "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0", "-b:v", "0", "-crf", "24", "-row-mt", "1",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"], out)


def _gif(out, w, h, fps, depth, first):
    return {"program": str(find_exe()), "args": ["encode-gif", out, str(w), str(h), str(fps)]}


def _png(out, w, h, fps, depth, first):
    return {"program": str(find_exe()), "args": ["encode-png", out, str(w), str(h), str(depth), str(first)]}


FORMATS: dict[str, Format] = {
    "mp4": Format(".mp4", False, (8,), _mp4),
    "prores4444": Format(".mov", True, (16,), _prores),
    "webm": Format(".webm", True, (8,), _webm),
    "gif": Format(".gif", True, (8,), _gif),
    "png": Format(".png", True, (8, 16), _png, video=False),
}


def get(name: str) -> Format:
    if name not in FORMATS:
        raise ValueError(f"unknown export format '{name}'; choose one of {', '.join(FORMATS)}")
    return FORMATS[name]
