"""What this engine does not draw yet, said in the reply when a film's markup uses it (measured against Chrome:
results/2d-markup-design/capability/CAPABILITY.md). Notes only: the markup is drawn as written."""
from __future__ import annotations

import re

_SVG = re.compile(r"<svg\b.*?</svg>", re.S)
_INNER_TAG = r"<(?!svg\b)[a-zA-Z][\w-]*\b[^>]*"
# (pattern, where: "svg" = inside <svg> pictures only, "all" = anywhere, what to say)
CHECKS = [
    (re.compile(_INNER_TAG + r"\s(?:filter|mask)\s*=\s*\"url\("), "svg",
     "a filter= or mask= on a shape inside an <svg> is not drawn by this engine yet; put the filter on the <svg> itself "
     "or on a <div> as style=\"filter:url(#id)\" (look_film {guide: \"what the engine draws\"})"),
    (re.compile(r"<clipPath\b[^>]*>(?:(?!</clipPath>).)*<text\b", re.S), "svg",
     "a <clipPath> made of <text> clips nothing yet (the clipped shape is drawn whole); words filled with a picture, "
     "gradient or moving shapes: CSS background-clip: text on an HTML element (its background shows through the letters)"),
    (re.compile(r"\bmask(?:-image)?\s*:\s*url\(\s*['\"]?#"), "all",
     "a CSS mask from an SVG <mask> (mask: url(#id)) hides the element entirely in this engine; gradient mask-image "
     "works, and CSS background-clip: text for words"),
    (re.compile(r"<pattern\b"), "svg", "SVG <pattern> fills draw as a flat colour; use CSS backgrounds or repeat shapes in Python"),
    (re.compile(r"<feDropShadow\b"), "all", "feDropShadow is not read; build it from feGaussianBlur + feOffset + feFlood + "
                                            "feComposite + feMerge, or use CSS filter: drop-shadow()"),
    (re.compile(r"<foreignObject\b"), "svg", "<foreignObject> draws nothing; place the HTML beside the <svg> instead"),
    (re.compile(_INNER_TAG + r"style\s*=\s*\"[^\"]*\btransform\s*:"), "svg",
     "CSS transform in a style inside an <svg> is ignored; use the transform=\"…\" attribute (keys' x / y / rotate / scale write it)"),
]


def notes(markup: str) -> list[str]:
    inner = "".join(re.sub(r"^<svg\b[^>]*>", "", s) for s in _SVG.findall(markup))
    return [say for rx, where, say in CHECKS if rx.search(inner if where == "svg" else markup)]
