"""What the Export sheet shows for 2D, as rows (exporter.py holds the job): "What for" in words, the chosen format's
settings, only the ones that apply to it (from io/formats.py data, nothing placed per format here), and the result read
back from the file. The range (everything, marker to marker) is the kit sheet's own row."""
from __future__ import annotations

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


def settings(row: dict, values: dict) -> list[dict]:
    """{key, kind toggle|choice|number, label, value, …} for the format `row` (exporting.info)."""
    out = []
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
        if values.get("estimate"):
            out.append({"key": "estimate", "kind": "note", "label": "File size", "value": values["estimate"]})
    if "sound" in values:                         # only an MP4 of a project that has sound (exporter.chose)
        out.append({"key": "sound", "kind": "toggle", "label": "Project sound", "value": values["sound"]})
    return out


def megabytes(n: int) -> str:
    return f"{n / 1e6:.1f} MB" if n >= 1e5 else f"{max(1, round(n / 1e3))} KB"


def gif_estimate(w: int, h: int, fps: float, seconds: float, values: dict) -> str:
    """"about 3.2 MB · 960×540 · 15 frames a second", worked out from the GIF's choices (no picture is drawn for it)."""
    ow, oh, ofps, n = table.gif_shape(w, h, fps, max(1, round(seconds * fps)), values["size"], values["rate"])
    return f"about {megabytes(table.gif_estimate(w, h, fps, seconds, values['size'], values['rate']))} · {ow}×{oh} · {n} frames"


def facts(row: dict, f: dict, path: str) -> list[dict]:
    """The finished file in words: [{label, text}]. Its name and folder are the sheet's Where (not said twice)."""
    out = [{"label": "Frames", "text": f'{f["frames"]} at {f["fps"]:g} fps'}]
    c = f.get("checked") or {}
    if c.get("size"):
        out.append({"label": "Size", "text": "×".join(str(n) for n in c["size"])})
    if isinstance(c.get("layers"), list):                     # motion samples: which layers, how often
        out.append({"label": "Moving layers", "text": ", ".join(c["layers"])})
        out.append({"label": "Samples", "text": f'{c["samples"]} each, {c["rate"]:g} a second'})
    if row["alpha"]:
        out.append({"label": "Transparency", "text": "kept" if f["alpha"] else "not kept"})
    if len(row["depths"]) > 1:
        out.append({"label": "Bit depth", "text": f'{f["depth"]}-bit'})
    if f.get("sound"):
        out.append({"label": "Sound", "text": "the project's mix"})
    if f.get("quality"):
        out.append({"label": "Quality", "text": f'{f["quality"]} (each frame gets what it needs)'})
    if f.get("encoded"):
        out.append({"label": "Encoded", "text": f["encoded"]})
    if f.get("kbps"):
        out.append({"label": "Bitrate", "text": f'{f["kbps"] / 1000:.1f} Mbit/s'})
    return out
