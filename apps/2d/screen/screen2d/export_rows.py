"""What the Export sheet shows for 2D, as rows (exporter.py holds the job): "What for" in words, the chosen format's
settings, only the ones that apply to it (from io/formats.py data, nothing placed per format here), and the result read
back from the file. The range (everything, marker to marker) is the kit sheet's own row."""
from __future__ import annotations

from pathlib import Path

from rostrum2d.io import formats as table

# What each format is for, in words; its file type beside it, one way for all (MP4, PNG …: a frames folder's rows say
# "frames" in their words). A format not named here shows its own label.
WHAT_FOR = {"mp4": "Video to share", "prores4444": "Video for editing, with transparency", "webm": "Video for the web",
            "gif": "Moving picture for a chat or a page", "png": "Still frames", "exr": "Frames for the Editor",
            "lottie": "Animation for apps and websites", "motion": "Motion for RostrumSound"}


def what_for(formats: list[dict]) -> list[dict]:
    """[{value, label, type}] for the sheet's list, in exporting.formats() order."""
    return [{"value": f["name"], "label": WHAT_FOR.get(f["name"], f["label"]),
             "type": (f["ext"] or f["label"].split()[0]).lstrip(".").upper()}
            for f in formats]


AREAS = {"frame": "Frame", "items": "Picked layers", "world": "Everything"}


def settings(row: dict, values: dict, picked: bool = False) -> list[dict]:
    """{key, kind toggle|choice|number, label, value, …} for the format `row` (exporting.info). `picked`: layers are picked, so a
    picture's Area can be them."""
    out = []
    if "area" in values:                          # a picture: the frame, or an area of the world (mcp/export_area.py)
        out.append({"key": "area", "kind": "choice", "label": "Area", "value": values["area"],
                    "options": [{"value": k, "label": w} for k, w in AREAS.items() if k != "items" or picked]})
    if row["alpha"]:
        out.append({"key": "alpha", "kind": "toggle", "label": "Transparency", "value": values["alpha"]})
    if len(row["depths"]) > 1:
        out.append({"key": "depth", "kind": "choice", "label": "Bit depth", "value": str(values["depth"]),
                    "options": [{"value": str(d), "label": f"{d}-bit"} for d in row["depths"]]})
    if row["qualities"]:
        out.append({"key": "quality", "kind": "choice", "label": "Quality", "value": values["quality"],
                    "options": [{"value": q, "label": q.capitalize()} for q in row["qualities"]]})
    if "size" in values:                          # a GIF: its size and rate, then what they come to (exporter.chose)
        for key, label, words in (("size", "Size", table.GIF_SIZES), ("rate", "Frame rate", table.GIF_RATES)):
            out.append({"key": key, "kind": "choice", "label": label, "value": values[key],
                        "options": [{"value": k, "label": w} for k, w in words.items()]})
        if values.get("file"):                    # what they come to (gif_line); gone once the result line says it
            out.append({"key": "file", "kind": "note", "label": "File", "value": values["file"]})
    if "sound" in values:                         # only an MP4 of a project that has sound (exporter.chose)
        out.append({"key": "sound", "kind": "toggle", "label": "Project sound", "value": values["sound"]})
    return out


def megabytes(n: int) -> str:
    return f"{n / 1e6:.1f} MB" if n >= 1e5 else f"{max(1, round(n / 1e3))} KB"


def line(weight: str, size, frames: int, fps: float, seconds: float | None = None) -> str:
    """The file in one line, the one way the sheet says it, before (the estimate) and after (the result):
    "about 9 KB · 960×540 · 150 frames at 15 fps". `size`: (w, h) or None. A GIF gives `seconds` and says its length
    instead of a frame count: it stores identical neighbouring frames once, so its picture count is never the frames
    played (the length is exact, and is what the export checks)."""
    parts = [weight] + (["×".join(map(str, size))] if size else []) +         [f"{seconds:.3g} s at {fps:g} fps" if seconds is not None else f"{frames} frames at {fps:g} fps"]
    return " · ".join(p for p in parts if p)


def gif_line(w: int, h: int, fps: float, seconds: float, values: dict, found) -> str:
    """Before export: what the GIF's choices come to. `found`: its measured bytes (gif_guess), None while being worked
    out, or the failure in words."""
    ow, oh, ofps, n = table.gif_shape(w, h, fps, max(1, round(seconds * fps)), values["size"], values["rate"])
    weight = (f"about {megabytes(found)}" if isinstance(found, int) else "Working out the size…" if found is None else found)
    return line(weight, (ow, oh), n, ofps, seconds)


def result(f: dict) -> str:
    """After export: the file as written (its bytes on disk, its size and frames read back): the sheet's result line."""
    weight = sum(Path(x).stat().st_size for x in f.get("files") or [] if Path(x).is_file())
    return line(megabytes(weight) if weight else "", (f.get("checked") or {}).get("size"), f["frames"], f["fps"], f.get("seconds"))


def facts(f: dict) -> list[dict]:
    """What the finished file holds that neither the result line (weight, size, frames: result()) nor the settings rows
    above (transparency, bit depth, quality, sound) already say: [{label, text}]."""
    out = []
    c = f.get("checked") or {}
    if isinstance(c.get("layers"), list):                     # motion samples: which layers, how often
        out.append({"label": "Moving layers", "text": ", ".join(c["layers"])})
        out.append({"label": "Samples", "text": f'{c["samples"]} each, {c["rate"]:g} a second'})
    if f.get("encoded"):
        out.append({"label": "Encoded", "text": f["encoded"]})
    if f.get("kbps"):
        out.append({"label": "Bitrate", "text": f'{f["kbps"] / 1000:.1f} Mbit/s'})
    return out
