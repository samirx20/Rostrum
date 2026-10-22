"""What the Export panel shows, as rows (exporter.py holds the job): the chosen format's settings, only the ones that
apply to it (from io/formats.py data, nothing placed per format here), and the result read back from the file."""
from __future__ import annotations


def settings(row: dict, values: dict, duration: float) -> list[dict]:
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
    if row["range"]:
        for key, label in (("start", "From"), ("end", "To")):
            out.append({"key": key, "kind": "number", "label": label, "value": values[key], "from": 0.0, "to": duration,
                        "unit": "s"})
    return out


def facts(row: dict, f: dict, path: str) -> list[dict]:
    """The finished file in words: [{label, text}]."""
    out = [{"label": "File", "text": path}, {"label": "Frames", "text": f'{f["frames"]} at {f["fps"]:g} fps'}]
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
    if f.get("kbps"):
        out.append({"label": "Bitrate", "text": f'{f["kbps"] / 1000:.1f} Mbit/s'})
    return out
