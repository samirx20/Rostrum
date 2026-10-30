"""Icons in HTML the way web pages write them, made inline SVG (for a page drawn without the icon sets' scripts):

    <i data-lucide="arrow-right"></i>               Lucide's web way (lucide.createIcons())
    <i class="ti ti-heart"></i>                      Tabler's web font way
    <iconify-icon icon="tabler:heart"></iconify-icon> / <span class="iconify" data-icon="lucide:x"></span>

The element's other attributes (class, style, width, height …) move onto the <svg>. `currentColor` becomes the colour
the element's own style gives (`style="color: #fff"`), else stays `currentColor`. A name no set has raises
IconNotFound (the five nearest names)."""
from __future__ import annotations

import re

from .icons import icon

_TAG = re.compile(r"<(i|span|iconify-icon)\b([^>]*)>\s*</\1>|<(i|span|iconify-icon)\b([^>]*?)/>", re.S)
_ATTR = re.compile(r'([\w:-]+)\s*=\s*("([^"]*)"|\'([^\']*)\')')


def _name(attrs: dict[str, str]) -> str | None:
    for k in ("data-lucide", "icon", "data-icon"):
        if attrs.get(k):
            return ("lucide:" if k == "data-lucide" else "") + attrs[k]
    classes = attrs.get("class", "").split()
    if "ti" in classes:
        named = [c[3:] for c in classes if c.startswith("ti-")]
        return f"tabler:{named[0]}" if named else None
    return None


def _swap(m: re.Match) -> str:
    raw = m.group(2) if m.group(1) else m.group(4)
    attrs = {a.group(1): a.group(3) if a.group(3) is not None else a.group(4) for a in _ATTR.finditer(raw or "")}
    name = _name(attrs)
    if name is None:
        return m.group(0)
    color = re.search(r"(?:^|;)\s*color\s*:\s*([^;]+)", attrs.get("style", ""))
    svg = icon(name, color=color.group(1).strip() if color else None)
    keep = {k: v for k, v in attrs.items() if k not in ("data-lucide", "icon", "data-icon")}
    if "class" in keep:
        keep["class"] = " ".join(c for c in keep["class"].split() if c not in ("ti", "iconify") and not c.startswith("ti-"))
    for k in ("width", "height"):
        if k in keep:
            svg = re.sub(rf'(<svg[^>]*?) {k}="[^"]*"', r"\1", svg, count=1)
    extra = "".join(f' {k}="{v}"' for k, v in keep.items() if v)
    return svg.replace("<svg", "<svg" + extra, 1)


def expand_icons(html: str) -> str:
    """The page with every icon element (see the module header) replaced by the icon's inline SVG."""
    if "lucide" not in html and "ti-" not in html and "icon" not in html:
        return html
    return _TAG.sub(_swap, html)
