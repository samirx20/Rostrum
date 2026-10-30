"""The app's shipped fonts (apps/2d/engine/fonts/, all variable) as @font-face rules for a markup film's page: only the
families the film names, each embedded once (data: URL), so HTML text and inline SVG <text> both find them."""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

from rostrum_core.byname import face_css as google_face_css, families_in_css

from .. import settings

FAMILIES = {"Inter": "InterVariable", "Roboto Flex": "RobotoFlex", "Recursive": "Recursive", "Montserrat": "Montserrat",
            "Source Serif 4": "SourceSerif4", "Fraunces": "Fraunces", "JetBrains Mono": "JetBrainsMono", "Caveat": "Caveat"}


def folder() -> Path:
    return settings.APP / "engine" / "fonts"


@lru_cache(maxsize=32)
def _data(path: str) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


def face_css(text: str = "") -> str:
    """@font-face rules for every app family named in `text` (Inter always: the page's default)."""
    out = []
    for family, stem in FAMILIES.items():
        if family != "Inter" and family not in text:
            continue
        # Italic faces only when the film asks for italic: with both files under one family, SVG <text> picked the
        # italic one (capability probe, 2026-10-30).
        for italic in (False, True) if "italic" in text else (False,):
            p = folder() / f"{stem}{'-Italic' if italic else ''}.ttf"
            if p.is_file():
                out.append(f'@font-face {{ font-family: "{family}"; font-weight: 100 1000; font-style: '
                           f'{"italic" if italic else "normal"}; src: url("data:font/ttf;base64,{_data(str(p))}"); }}')
    for family, ask in families_in_css(text).items():       # any Google Fonts family by name (rostrum_core.byname)
        if family not in FAMILIES:                           # italic faces only when asked, as above
            italic = ask["italic"] if ask["italic"] is not None else (None if "italic" in text else False)
            out.append(google_face_css(family, ask["weights"], italic))
    return "\n".join(out)


def families() -> list[str]:
    return list(FAMILIES)
