"""What this engine does not draw yet, said in the reply when a film's markup uses it (measured against Chrome:
results/2d-markup-design/capability/CAPABILITY.md). Notes only: the markup is drawn as written."""
from __future__ import annotations

import re

_SVG = re.compile(r"<svg\b.*?</svg>", re.S)
_INNER_TAG = r"<(?!svg\b)[a-zA-Z][\w-]*\b[^>]*"
# (pattern, where: "svg" = inside <svg> pictures only, "all" = anywhere, what to say)
CHECKS = [
    (re.compile(r"<pattern\b"), "svg", "SVG <pattern> fills draw as a flat colour; use CSS backgrounds or repeat shapes in Python"),
    (re.compile(r"<fe(DiffuseLighting|SpecularLighting|ConvolveMatrix|Tile)\b"), "all",
     "feDiffuseLighting, feSpecularLighting, feConvolveMatrix and feTile are not drawn by this engine yet (each passes "
     "its input through); light with gradients, blurs and blend modes instead"),
    (re.compile(_INNER_TAG + r"\sfilter\s*=\s*\"url\("), "feimage",
     "an feImage in a filter= on a shape inside an <svg> draws nothing yet; use that filter on a <div> as "
     "style=\"filter:url(#id)\", where feImage is drawn"),
    (re.compile(r"<foreignObject\b"), "svg", "<foreignObject> draws nothing; place the HTML beside the <svg> instead"),
    (re.compile(_INNER_TAG + r"style\s*=\s*\"[^\"]*\btransform\s*:"), "svg",
     "CSS transform in a style inside an <svg> is ignored; use the transform=\"…\" attribute (keys' x / y / rotate / scale write it)"),
]


def notes(markup: str) -> list[str]:
    inner = "".join(re.sub(r"^<svg\b[^>]*>", "", s) for s in _SVG.findall(markup))
    return [say for rx, where, say in CHECKS
            if (where != "feimage" or "<feImage" in inner) and rx.search(inner if where in ("svg", "feimage") else markup)]
