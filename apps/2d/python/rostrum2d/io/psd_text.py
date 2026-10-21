"""PSD text layer → a 2D text node (psd-tools' engine data: font, size, colour, alignment, transform, text with its line
breaks). Returns None, with the reason in the report, when it can't be a real text (font not in the app, mixed styles,
turned or skewed): the caller then keeps the layer's pixels. The font is looked up through importing.app_fonts (the one list).
"""
from __future__ import annotations

import math
import re

_WEIGHTS = {"thin": 100, "hairline": 100, "extralight": 200, "ultralight": 200, "light": 300, "regular": 400, "roman": 400,
            "book": 400, "normal": 400, "medium": 500, "semibold": 600, "demibold": 600, "bold": 700, "extrabold": 800,
            "ultrabold": 800, "heavy": 800, "black": 900}
_ALIGN = {0: "left", 1: "right", 2: "center"}               # Justification; 3+ are the justified ones (drawn left)
_SAME = ("Font", "FontSize", "FillColor", "Tracking", "Leading", "AutoLeading", "FauxBold", "FauxItalic")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _family(postscript: str, fonts: set[str]) -> tuple[str | None, str]:
    """('Inter', 'Bold') from 'Inter-Bold': the app's family spelling for a PostScript name, and its style words."""
    family, _, style = str(postscript).partition("-")
    by_norm = {_norm(f): f for f in fonts}
    return by_norm.get(_norm(family)), style


def _hex(fill: dict) -> str | None:
    if fill.get("Type") != 1 or len(fill.get("Values", ())) != 4:         # RGB only: [alpha, r, g, b]
        return None
    return "#" + "".join(f"{round(max(0.0, min(1.0, float(v))) * 255):02x}" for v in fill["Values"][1:])


def text_node(layer, fonts: set[str] | None, report: list) -> dict | None:
    name = layer.name
    try:
        ed, rd, m = layer.engine_dict, layer.resource_dict, layer.transform
    except Exception as e:
        report.append(f"text '{name}': its type data could not be read ({e}); kept as a picture")
        return None
    runs = [r["StyleSheet"]["StyleSheetData"] for r in ed["StyleRun"]["RunArray"]]
    if any(any(r.get(k) != runs[0].get(k) for k in _SAME) for r in runs):
        report.append(f"text '{name}': more than one font / size / colour inside the layer; kept as a picture")
        return None
    st = runs[0]
    if abs(m[1]) > 1e-3 or abs(m[2]) > 1e-3:
        report.append(f"text '{name}': turned or skewed in the PSD; kept as a picture")
        return None
    ps_name = str(rd["FontSet"][st["Font"]]["Name"]).strip("'\"")      # the engine data's string reads back quoted
    family, style = _family(ps_name, fonts) if fonts is not None else (ps_name.partition("-")[0], ps_name.partition("-")[2])
    if family is None:
        report.append(f"text '{name}': font '{ps_name}' not installed: kept as a picture")
        return None
    colour = _hex(st.get("FillColor", {}))
    if colour is None:
        report.append(f"text '{name}': its colour is not RGB; kept as a picture")
        return None
    words = [w.lower() for w in re.findall(r"[A-Z][a-z]*|[a-z]+", style)]
    weight = max([_WEIGHTS.get("".join(words[i:j]), 0) for i in range(len(words)) for j in range(i + 1, len(words) + 1)] or [0]) or 400
    weight = 700 if st.get("FauxBold") else weight
    if st.get("FauxItalic") or "italic" in words or "oblique" in words:
        report.append(f"text '{name}': italic is not carried; drawn upright")
    size = float(st["FontSize"]) * math.hypot(m[2], m[3])
    para = ed["ParagraphRun"]["RunArray"][0]["ParagraphSheet"]["Properties"]
    props = {"body": str(layer.text).replace("\r\n", "\n").replace("\r", "\n").rstrip("\n"), "size": round(size, 3),
             "weight": float(weight), "color": colour, "font": family, "align": _ALIGN.get(para.get("Justification", 0), "left"),
             "tracking": round(st.get("Tracking", 0) / 1000, 4),
             "lineHeight": 1.2 if st.get("AutoLeading", True) else round(float(st["Leading"]) / float(st["FontSize"]), 3)}
    l, t, r, b = layer.bbox
    return {"type": "text", "name": name, "box": [l, t, r - l, b - t], "props": props}
