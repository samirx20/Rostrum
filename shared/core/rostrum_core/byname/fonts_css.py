"""Google Fonts the way web code asks for them, and handed to an engine.

    families_in_css(css)  -> {"Inter": {"weights": {400, 700} | None, "italic": None}, …}: the families a stylesheet
                             names (`font-family: "Inter", sans-serif`, an @import / <link> fonts.googleapis.com URL)
                             that are Google Fonts families; generic and other names are left alone
    google_css_url(url)   -> the same for one fonts.googleapis.com/css2 (or css) URL, its weights and italics
    face_css(family, weights, italic) -> @font-face rules (data: URLs) for a page to embed
    engine_font(family)   -> ONE file holding every face of the family (a .ttc collection when it has several), for an
                             engine that takes one file per family (the 2D engine's scene `fonts`)
"""
from __future__ import annotations

import base64
import re
import urllib.parse
from pathlib import Path

from ..cache import CACHE
from .fonts import KIND, _family, faces, font_files, google_family

_GENERIC = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui", "ui-sans-serif", "ui-serif",
            "ui-monospace", "emoji", "math", "inherit", "initial", "unset"}


def google_css_url(url: str) -> dict[str, dict]:
    """fonts.googleapis.com/css2?family=Inter:ital,wght@0,400;1,700&family=Lato -> weights / italic per family."""
    out = {}
    for spec in urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("family", []):
        for one in spec.split("|"):                                       # the old /css API: family=A|B:400,700i
            name, _, axes = one.partition(":")
            family = google_family(name)
            if family is None:
                continue
            weights, italics = set(), set()
            if "@" in axes:                                               # css2: ital,wght@0,400;1,700 or wght@100..900
                tags, _, values = axes.partition("@")
                tags = tags.split(",")
                for tup in values.split(";"):
                    v = dict(zip(tags, tup.split(",")))
                    if "wght" in v and ".." not in v["wght"]:
                        weights.add(float(v["wght"]))
                    italics.add(v.get("ital", "0") == "1")
            elif axes:                                                    # css: 400,700italic / 400i
                for v in axes.split(","):
                    weights.add(float(re.match(r"\d*", v).group() or 400))
                    italics.add(bool(re.search(r"i", v)))
            out[family] = {"weights": weights or None, "italic": None if len(italics) != 1 else italics.pop()}
    return out


def families_in_css(css: str) -> dict[str, dict]:
    """Every Google Fonts family a stylesheet (or page) names; each with the weights / italic its URL asks for, or
    None (= every face)."""
    out = {}
    for url in re.findall(r"""https?://fonts\.googleapis\.com/css2?\?[^"')\s>]+""", css):
        out.update(google_css_url(url.replace("&amp;", "&")))
    for decl in re.findall(r"font-family\s*[:=]\s*([^;}{>]+)", css):
        for name in decl.split(","):
            name = name.strip().strip("'\"").strip()
            if name.lower() not in _GENERIC and (family := google_family(name)) and family not in out:
                out[family] = {"weights": None, "italic": None}
    return out


def face_css(name: str, weights=None, italic: bool | None = None) -> str:
    """@font-face rules for the family's chosen faces, each file embedded as a data: URL."""
    family = _family(name)
    by_file = {f["file"]: f for f in faces(family)}
    rules = []
    for path in font_files(family, weights, italic):
        f = by_file[path.name]
        lo, hi = f["weight"]
        weight = f"{lo:g}" if lo == hi else f"{lo:g} {hi:g}"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        rules.append(f'@font-face {{ font-family: "{family}"; font-weight: {weight}; font-style: '
                     f'{"italic" if f["italic"] else "normal"}; src: url("data:font/ttf;base64,{data}"); }}')
    return "\n".join(rules)


def engine_font(name: str) -> Path:
    """One file with every face of the family: the file itself when there is one, else a collection (.ttc) made once
    with fontTools (MIT) and kept in the shared cache beside the files."""
    family = _family(name)
    files = font_files(family)
    if len(files) == 1:
        return files[0]
    key = f"{files[0].parent.name.split('--')[0]}--collection-{len(files)}"
    target = "family.ttc"
    folder = CACHE.get(KIND, key) or CACHE.put(KIND, key, lambda tmp: _collect(files, tmp / target), {"family": family})
    return folder / target


def _collect(files: list[Path], out: Path) -> None:
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.ttCollection import TTCollection
    collection = TTCollection()
    collection.fonts = [TTFont(str(p)) for p in files]
    collection.save(str(out), shareTables=True)
