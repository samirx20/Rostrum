"""Reads an export back and fails loudly: frame count, size and alpha must be what was asked for."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image


class ExportError(RuntimeError):
    def __init__(self, message: str, facts: dict):
        super().__init__(f"{message}; read back: {facts}")
        self.facts = facts


def _run(args: list[str]) -> bytes:
    r = subprocess.run(args, capture_output=True)
    if r.returncode:
        raise ExportError(f"{args[0]} failed: {r.stderr.decode(errors='replace').strip()}", {"command": args[:4]})
    return r.stdout


def _probe(path: Path) -> dict:
    out = _run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                "stream=width,height,pix_fmt,nb_read_frames", "-of", "json", str(path)])
    s = json.loads(out)["streams"][0]
    return {"frames": int(s["nb_read_frames"]), "size": (s["width"], s["height"]), "pix_fmt": s["pix_fmt"]}


def _video_frame_alpha(path: Path, index: int, w: int, h: int) -> int:
    """Lowest alpha of video frame `index`, decoded to rgba (webm: vp9's own decoder; the native one drops alpha)."""
    pre = ["-c:v", "libvpx-vp9"] if path.suffix == ".webm" else []
    raw = _run(["ffmpeg", "-v", "error", *pre, "-i", str(path), "-vf", f"select='eq(n,{index})'", "-frames:v", "1",
                "-f", "rawvideo", "-pix_fmt", "rgba", "-"])
    if len(raw) != w * h * 4:
        raise ExportError(f"could not decode frame {index}", {"file": str(path)})
    return int(np.frombuffer(raw, np.uint8)[3::4].min())


def _png_bits(path: Path) -> int:
    return path.read_bytes()[24]               # IHDR bit depth


def _picks(n: int) -> list[int]:
    return sorted({0, n // 2, n - 1})


def _gif_facts(path: Path) -> dict:
    with Image.open(path) as im:
        n, size = im.n_frames, im.size
        low = 255
        for i in _picks(n):
            im.seek(i)
            low = min(low, int(np.asarray(im.convert("RGBA"))[..., 3].min()))
    return {"frames": n, "size": size, "min_alpha": low}


def _png_facts(out: Path) -> dict:
    rx = re.compile(re.escape(out.name).replace(re.escape("{frame}"), r"\d+") + "$")
    files = sorted(p for p in out.parent.iterdir() if rx.match(p.name))
    facts = {"frames": len(files), "size": None, "min_alpha": 255, "bits": None}
    for p in (files[0], files[-1]) if files else ():
        with Image.open(p) as im:
            facts["size"] = im.size
            facts["bits"] = _png_bits(p)
            facts["min_alpha"] = min(facts["min_alpha"], int(np.asarray(im.convert("RGBA"))[..., 3].min()))
    return facts


def check(fmt: str, out: str | Path, frames: int, w: int, h: int, alpha: bool, depth: int = 8) -> dict:
    """Facts about the exported file(s); raises ExportError when they don't match what was asked for.
    `out` is the file, or for png the pattern holding {frame}."""
    out = Path(out)
    if fmt == "png":
        facts = _png_facts(out)
        if facts["bits"] is not None and facts["bits"] != depth:
            raise ExportError(f"PNG is {facts['bits']}-bit, asked {depth}", facts)
    elif fmt == "gif":
        facts = _gif_facts(out)
    else:
        facts = _probe(out)
        facts["min_alpha"] = 255
        pf = facts["pix_fmt"]
        if "yuva" in pf or pf.startswith(("rgba", "bgra", "argb")) or fmt == "webm":    # has an alpha channel
            facts["min_alpha"] = min(_video_frame_alpha(out, i, w, h) for i in _picks(facts["frames"]))
        elif alpha:
            raise ExportError(f"alpha was asked for but the file's pixel format {facts['pix_fmt']} has none", facts)
    if facts["frames"] != frames:
        raise ExportError(f"expected {frames} frames, the file has {facts['frames']}", facts)
    if facts["size"] != (w, h):
        raise ExportError(f"expected {w}x{h}, the file is {facts['size']}", facts)
    if alpha and facts["min_alpha"] >= 255:
        raise ExportError("alpha was asked for but every checked pixel is opaque", facts)
    if not alpha and facts["min_alpha"] < 255:
        raise ExportError("alpha was not asked for but the file has transparent pixels", facts)
    return facts
