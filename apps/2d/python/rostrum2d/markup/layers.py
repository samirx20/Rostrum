"""Split an inline <svg> into stacked page layers, so the engine's shaders (light) can run on parts inside it.

The engine runs filters on page layers (HTML boxes, a whole <svg>), not on shapes inside one SVG picture. So an <svg>
with lit parts becomes copies of itself, stacked in paint order in the svg's own place: each lit part gets its own
copy (the part, its ancestor <g>s with their transforms, every <defs>/<style> kept, everything else left out), and
each run of unlit content between lit parts gets one plain copy. Same attributes, viewBox and size in every copy, so
every shape lands exactly where it was drawn; z-order is unchanged. Duplicate ids across copies are the same
definitions, so gradients and clips still resolve.

Lit parts: any element inside the <svg> marked `data-light` (any depth), and, when the <svg> itself is marked, each of
its direct children (own `data-light` settings on a child win over the svg's).
"""
from __future__ import annotations

import re

_TOKEN = re.compile(r"<!--.*?-->|<!\[CDATA\[.*?\]\]>|</\s*([A-Za-z][\w:.-]*)\s*>"
                    r"|<([A-Za-z][\w:.-]*)((?:[^>\"']|\"[^\"]*\"|'[^']*')*?)(/?)>|[^<]+|<", re.S)
_LIGHT_ATTR = re.compile(r"\s+data-light(?:\s*=\s*(\"[^\"]*\"|'[^']*'))?")
_GRAIN_ATTR = re.compile(r"\s+data-grain(?:\s*=\s*(\"[^\"]*\"|'[^']*'))?")
_STYLE_ATTR = re.compile(r"\s+style\s*=\s*(\"[^\"]*\"|'[^']*')")
_CLASS_ATTR = re.compile(r"\s+class\s*=\s*(\"[^\"]*\"|'[^']*')")
_ID_ATTR = re.compile(r"\sid\s*=\s*[\"']([^\"']*)[\"']")
_REF = re.compile(r"(?:href\s*=\s*[\"']#|url\(\s*[\"']?#)([^\"')\s]+)")
# Never painted: kept in every copy so references resolve.
KEEP = {"defs", "style", "title", "desc", "metadata", "lineargradient", "radialgradient", "clippath", "mask",
        "filter", "pattern", "marker", "symbol"}
# Placement and look of the svg as one picture: these go on the box holding the copies (opacity on each copy
# would show the parts through each other).
_BOX_PROPS = {"position", "left", "top", "right", "bottom", "inset", "z-index", "transform", "transform-origin",
              "opacity", "margin", "margin-left", "margin-right", "margin-top", "margin-bottom", "filter",
              "mix-blend-mode", "translate", "rotate", "scale", "float", "grid-area", "flex"}


class Node:
    __slots__ = ("tag", "attrs", "close", "children", "text", "light", "owner", "unit")

    def __init__(self, tag=None, attrs="", close="", text=None):
        self.tag, self.attrs, self.close, self.text = tag, attrs, close, text
        self.children: list[Node] = []
        self.light = None          # this element's own data-light text ("" when bare), or None
        self.owner = None          # the lit part a unit belongs to (a Node), or None
        self.unit = False


def parse(inner: str) -> list[Node]:
    """The content of an <svg> as a tree (text and comments are leaves)."""
    root = Node("#root")
    stack = [root]
    for m in _TOKEN.finditer(inner):
        end, tag = m.group(1), m.group(2)
        if end:
            name = end.lower()
            for i in range(len(stack) - 1, 0, -1):
                if stack[i].tag.lower() == name:
                    del stack[i:]
                    break
            continue
        if tag:
            n = Node(tag, m.group(3), m.group(4))
            lm = _LIGHT_ATTR.search(n.attrs)
            if lm:
                n.light = (lm.group(1) or '""')[1:-1]
                n.attrs = n.attrs[:lm.start()] + n.attrs[lm.end():]
            stack[-1].children.append(n)
            if not n.close and tag.lower() not in ("br",):
                stack.append(n)
            continue
        stack[-1].children.append(Node(text=m.group(0)))
    return root.children


def _has_lit(n: Node) -> bool:
    return n.light is not None or any(_has_lit(c) for c in n.children)


def _source(n: Node) -> str:
    if n.tag is None:
        return n.text
    if n.close:
        return f"<{n.tag}{n.attrs}/>"
    return f"<{n.tag}{n.attrs}>" + "".join(_source(c) for c in n.children) + f"</{n.tag}>"


def _mark(nodes: list[Node], owner: Node | None, units: list[Node]):
    """Paint order: each unit (a subtree with no lit part inside, below its owner) in `units`, its owner set."""
    for n in nodes:
        if n.tag is None or n.tag.lower() in KEEP:
            continue
        own = n if n.light is not None else owner
        if any(_has_lit(c) for c in n.children):
            _mark(n.children, own, units)
        else:
            n.unit, n.owner = True, own
            units.append(n)


def _copy(nodes: list[Node], keep: set[int]) -> str:
    out = []
    for n in nodes:
        if n.tag is None:
            continue
        if n.tag.lower() in KEEP or id(n) in keep:
            out.append(_source(n))
        elif not n.unit and not n.close and _any_in(n, keep):
            out.append(f"<{n.tag}{n.attrs}>" + _copy(n.children, keep) + f"</{n.tag}>")
    return "".join(out)


def _any_in(n: Node, keep: set[int]) -> bool:
    return any(id(c) in keep or (not c.unit and _any_in(c, keep)) for c in n.children)


def runs(nodes: list[Node], whole: str | None) -> list[tuple[str | None, list[Node]]]:
    """[(light text or None, units)] in paint order; `whole` is the svg's own data-light (each direct child a part)."""
    if whole is not None:
        for c in nodes:
            if c.tag is not None and c.tag.lower() not in KEEP:
                c.light = whole + ";" + c.light if c.light is not None else whole
    units: list[Node] = []
    _mark(nodes, None, units)
    out: list[tuple[str | None, list[Node]]] = []
    for u in units:
        if out and u.owner is None and out[-1][0] is None:
            out[-1][1].append(u)
        elif out and u.owner is not None and out[-1][1][-1].owner is u.owner:
            out[-1][1].append(u)
        else:
            out.append((u.owner.light if u.owner is not None else None, [u]))
    return out


def _decls(style: str) -> list[tuple[str, str]]:
    return [(k.strip().lower(), v.strip()) for k, s, v in (d.partition(":") for d in style.split(";")) if s]


def split(start_attrs: str, inner: str, filter_for) -> str | None:
    """The <svg start_attrs>inner</svg> as stacked copies, each lit run in a box filtered by `filter_for(light text)`
    (a CSS `filter` value). None when nothing in it is lit."""
    whole = None
    lm = _LIGHT_ATTR.search(start_attrs)
    if lm:
        whole = (lm.group(1) or '""')[1:-1]
        start_attrs = start_attrs[:lm.start()] + start_attrs[lm.end():]
    nodes = parse(inner)
    if whole is None and not any(_has_lit(n) for n in nodes):
        return None
    parts = runs(nodes, whole)
    # The box takes the svg's place: its class, and the placing part of its style; the rest stays on each copy.
    box_style, own_style = [], []
    sm = _STYLE_ATTR.search(start_attrs)
    if sm:
        for k, v in _decls(sm.group(1)[1:-1]):
            (box_style if k in _BOX_PROPS else own_style).append(f"{k}: {v}")
        start_attrs = start_attrs[:sm.start()] + start_attrs[sm.end():]
    gm = _GRAIN_ATTR.search(start_attrs)          # grain on the svg as a whole: on the box (grain.py)
    grain = gm.group(0) if gm else ""
    if gm:
        start_attrs = start_attrs[:gm.start()] + start_attrs[gm.end():]
    cm = _CLASS_ATTR.search(start_attrs)
    klass = ""
    if cm:
        klass = f" class={cm.group(1)}"
        start_attrs = start_attrs[:cm.start()] + start_attrs[cm.end():]
    # Elements referenced by <use href="#id"> (or url(#id)) that a copy leaves out ride along unpainted in its <defs>.
    refs = set(_REF.findall(inner))
    by_id = {}
    if refs:
        def walk(ns):
            for n in ns:
                if n.tag is not None:
                    im = _ID_ATTR.search(n.attrs)
                    if im and im.group(1) in refs:
                        by_id[im.group(1)] = n
                    walk(n.children)
        walk(nodes)
    layers = []
    for i, (light, units) in enumerate(parts):
        keep = {id(u) for u in units}
        body = _copy(nodes, keep)
        extra = [_source(n) for n in by_id.values() if id(n) not in keep and n.tag.lower() not in KEEP]
        if extra:
            body = "<defs>" + "".join(extra) + "</defs>" + body
        css = "; ".join(own_style + ["display: block"])
        svg = f'<svg{start_attrs} style="{css}">{body}</svg>'
        place = "" if i == 0 else "position: absolute; left: 0; top: 0"
        if light is None:
            layers.append(svg if i == 0 else svg.replace(f'style="{css}"', f'style="{css}; {place}"', 1))
        else:
            layers.append(f'<div style="{place + "; " if place else ""}filter: {filter_for(light)}">{svg}</div>')
    # The copies stack inside their own positioned box, so the svg's class or style keeps placing the whole (an inline
    # `position: relative` on the outer box would beat a class's `position: absolute`).
    return (f'<div{klass}{grain} style="{"; ".join(box_style)}"><div style="position: relative">' + "".join(layers)
            + "</div></div>")

