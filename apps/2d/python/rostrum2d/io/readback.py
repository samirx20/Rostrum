"""Reads an export back and fails loudly: frame count, size and alpha must be what was asked for.

Alpha is checked as the file's shape, not its pixels: "transparency kept" means the file carries an alpha channel
(`alpha_channel`). Whether any pixel is see-through is the picture's business (a solid background is opaque
everywhere, and that file is right). Asked without alpha, the file must hold no see-through pixel."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from .. import settings


class ExportError(RuntimeError):
    def __init__(self, message: str, facts: dict):
        super().__init__(f"{message}; read back: {facts}")
        self.facts = facts


def _run(args: list[str]) -> bytes:
    r = subprocess.run(args, capture_output=True, creationflags=settings.NO_WINDOW)
    if r.returncode:
        raise ExportError(f"{args[0]} failed: {r.stderr.decode(errors='replace').strip()}", {"command": args[:4]})
    return r.stdout


def _probe(path: Path) -> dict:
    out = _run([settings.ffmpeg("ffprobe"), "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                "stream=width,height,pix_fmt,nb_read_frames", "-of", "json", str(path)])
    s = json.loads(out)["streams"][0]
    return {"frames": int(s["nb_read_frames"]), "size": (s["width"], s["height"]), "pix_fmt": s["pix_fmt"]}


def _video_frame_alpha(path: Path, index: int, w: int, h: int) -> int:
    """Lowest alpha of video frame `index`, decoded to rgba (webm: vp9's own decoder; the native one drops alpha)."""
    pre = ["-c:v", "libvpx-vp9"] if path.suffix == ".webm" else []
    raw = _run([settings.ffmpeg(), "-v", "error", *pre, "-i", str(path), "-vf", f"select='eq(n,{index})'", "-frames:v", "1",
                "-f", "rawvideo", "-pix_fmt", "rgba", "-"])
    if len(raw) != w * h * 4:
        raise ExportError(f"could not decode frame {index}", {"file": str(path)})
    return int(np.frombuffer(raw, np.uint8)[3::4].min())


def _png_header(path: Path) -> tuple[int, bool]:
    """(bit depth, has an alpha channel) from the IHDR: colour type 4 is grey + alpha, 6 is RGBA."""
    head = path.read_bytes()[:26]
    return head[24], head[25] in (4, 6)


def _picks(n: int) -> list[int]:
    return sorted({0, n // 2, n - 1})


def _gif_facts(path: Path) -> dict:
    with Image.open(path) as im:
        n, size = im.n_frames, im.size
        ms = 0
        for i in range(n):
            im.seek(i)
            ms += int(im.info.get("duration", 0))
        low = 255
        for i in _picks(n):
            im.seek(i)
            low = min(low, int(np.asarray(im.convert("RGBA"))[..., 3].min()))
    # A GIF's transparency is one palette slot, written when a pixel is see-through; an opaque picture needs none.
    return {"frames": n, "size": size, "min_alpha": low, "alpha_channel": True, "ms": ms}


def _png_facts(out: Path) -> dict:
    rx = re.compile(re.escape(out.name).replace(re.escape("{frame}"), r"\d+") + "$")
    files = sorted(p for p in out.parent.iterdir() if rx.match(p.name))
    facts = {"frames": len(files), "size": None, "min_alpha": 255, "bits": None, "alpha_channel": True}
    for p in (files[0], files[-1]) if files else ():
        with Image.open(p) as im:
            facts["size"] = im.size
            facts["bits"], has = _png_header(p)
            facts["alpha_channel"] = facts["alpha_channel"] and has
            facts["min_alpha"] = min(facts["min_alpha"], int(np.asarray(im.convert("RGBA"))[..., 3].min()))
    return facts


def _exr_facts(out: Path) -> dict:
    """The hand-off EXR sequence (HANDOFFS § 2): part `rgba`, half R G B A, ACEScg. Reads the first and last frames."""
    import OpenEXR                                   # BSD-3 (ASWF); only needed to check an EXR export
    rx = re.compile(re.escape(out.name).replace(re.escape("{frame}"), r"(\d+)") + "$")
    hits = sorted((int(m.group(1)), p) for p in out.parent.iterdir() if (m := rx.match(p.name)))
    nums = [n for n, _ in hits]
    facts = {"frames": len(hits), "size": None, "min_alpha": 255, "first": nums[0] if nums else None,
             "gaps": nums != list(range(nums[0], nums[0] + len(nums))) if nums else False, "alpha_channel": True}   # rgba part, checked below
    for _, p in (hits[0], hits[-1]) if hits else ():
        with OpenEXR.File(str(p)) as f:
            part = f.parts[0]
            h = part.header
            rgba = part.channels.get("RGBA")
            if rgba is None or rgba.pixels.dtype != np.float16 or h.get("name") != "rgba":
                raise ExportError(f"{p.name} has no half-float rgba part", {"channels": list(part.channels), "name": h.get("name")})
            px = rgba.pixels
            facts["size"] = (px.shape[1], px.shape[0])
            a = px[..., 3].astype(np.float32)
            if not np.isfinite(px.astype(np.float32)).all():
                raise ExportError(f"{p.name} holds NaN or infinite pixels", facts)
            facts["min_alpha"] = min(facts["min_alpha"], int(round(float(a.min()) * 255)))
    return facts


def check(fmt: str, out: str | Path, frames: int, w: int, h: int, alpha: bool, depth: int = 8, seconds: float | None = None) -> dict:
    """Facts about the exported file(s); raises ExportError when they don't match what was asked for.
    `out` is the file, or for png the pattern holding {frame}. A GIF merges identical neighbouring frames (fewer frames
    than asked is right) and must last `seconds`."""
    out = Path(out)
    if fmt == "png":
        facts = _png_facts(out)
        if facts["bits"] is not None and facts["bits"] != depth:
            raise ExportError(f"PNG is {facts['bits']}-bit, asked {depth}", facts)
    elif fmt == "exr":
        facts = _exr_facts(out)
        if facts["gaps"]:
            raise ExportError("the EXR sequence has missing frame numbers", facts)
    elif fmt == "gif":
        facts = _gif_facts(out)
    else:
        facts = _probe(out)
        facts["min_alpha"] = 255
        pf = facts["pix_fmt"]
        # webm: ffprobe names the colour stream's format (yuv420p); vp9 keeps alpha in a side stream, read by decoding
        facts["alpha_channel"] = "yuva" in pf or pf.startswith(("rgba", "bgra", "argb")) or fmt == "webm"
        if facts["alpha_channel"]:
            facts["min_alpha"] = min(_video_frame_alpha(out, i, w, h) for i in _picks(facts["frames"]))
    if fmt == "gif" and seconds is not None and abs(facts["ms"] - 1000 * seconds) > 30:
        raise ExportError(f"the GIF lasts {facts['ms'] / 1000:g} s, the scene {seconds:g} s", facts)
    if fmt == "gif" and 0 < facts["frames"] < frames:
        facts["merged"] = frames - facts["frames"]       # identical neighbours are stored once and last longer (the time is checked above)
    if facts["frames"] != frames and not (fmt == "gif" and 0 < facts["frames"] < frames):
        raise ExportError(f"expected {frames} frames, the file has {facts['frames']}", facts)
    if facts["size"] != (w, h):
        raise ExportError(f"expected {w}x{h}, the file is {facts['size']}", facts)
    if alpha and not facts["alpha_channel"]:
        raise ExportError("transparency was asked for but the file has no alpha channel", facts)
    if not alpha and facts["min_alpha"] < 255:
        raise ExportError("alpha was not asked for but the file has transparent pixels", facts)
    return facts
