"""The import tree → document operations. Every importer (svg, psd, pdf, figma) returns the same tree (see
`apps/2d/python/rostrum2d/io/README`-style note in the H9 brief): nodes with ABSOLUTE source boxes; this module
places them relative to their group, checks every field against fields.py and makes the calls. One `doc.apply`, one undo step.
"""
from __future__ import annotations

import re
from pathlib import Path

from rostrum_core.tree import index

from .. import fields as F
from .. import pathdata as PD
from ..kind import KIND

_SET_BY_TREE = {"x", "y", "anchorX", "anchorY"}
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_HEX_A = re.compile(r"^#[0-9a-fA-F]{8}$")
_COLOUR_ORDER = ("fill", "color", "strokeColor")        # whose alpha wins when they disagree
DEFAULT_FONT = F.defaults("text")["font"]


def _boxes(node: dict) -> list[float]:
    """The node's box; a group's is the union of its children's (computed once, stored on the node)."""
    if node["type"] == "group":
        kids = [_boxes(k) for k in node.get("layers", [])]
        if not kids:
            raise ValueError(f"group '{node.get('name')}' has no layers")
        x0, y0 = min(b[0] for b in kids), min(b[1] for b in kids)
        x1, y1 = max(b[0] + b[2] for b in kids), max(b[1] + b[3] for b in kids)
        node["box"] = [x0, y0, x1 - x0, y1 - y0]
    return node["box"]


def _id(name: str, type_: str, taken: set) -> str:
    base = re.sub(r"[^a-z0-9_]+", "_", (name or "").lower()).strip("_") or type_
    id_, n = base, 1
    while id_ in taken:
        n += 1
        id_ = f"{base}_{n}"
    taken.add(id_)
    return id_


def _colours(node: dict, props: dict, report: list):
    """Colours must be #rrggbb; an alpha (#rrggbbaa) folds into the layer's opacity."""
    names = {p.name for p in F.FIELDS[node["type"]] if p.type == "color"}
    alphas = {}
    for k in [k for k in props if k in names]:
        v = props[k]
        if _HEX_A.match(v):
            alphas[k] = int(v[7:9], 16) / 255
            props[k] = v[:7].lower()
        elif _HEX.match(v):
            props[k] = v.lower()
        else:
            raise ValueError(f"layer '{node['name']}': {k} {v!r} is not #rrggbb")
    if alphas:
        first = next((k for k in _COLOUR_ORDER if k in alphas), next(iter(alphas)))
        props["opacity"] = props.get("opacity", 1.0) * alphas[first]
        if len({round(a, 3) for a in alphas.values()}) > 1:
            report.append(f"'{node['name']}': fill and outline have different transparency; "
                          f"the layer uses the {first} one ({alphas[first]:.0%})")


def _props(node: dict, box: list, parent_box, fonts, report: list) -> dict:
    kind, props = node["type"], dict(node.get("props", {}))
    known = {p.name for p in F.FIELDS[kind]}
    for k in props:
        if k in _SET_BY_TREE:
            raise ValueError(f"layer '{node['name']}': {k} is set by the importer's tree, not by props")
        if k not in known:
            raise ValueError(f"layer '{node['name']}': '{k}' is not a {kind} field (fields.py)")
    _colours(node, props, report)
    ox, oy = parent_box[0], parent_box[1]
    if kind == "path":
        props["d"] = PD.write(PD.transformed(PD.commands(props["d"]), lambda x, y: (x - box[0], y - box[1])))
    if kind in ("path", "shape", "image", "group"):
        props.setdefault("w", max(box[2], 1.0 if kind == "path" else 0.0))
        props.setdefault("h", max(box[3], 1.0 if kind == "path" else 0.0))
    if kind == "text" and fonts is not None and props.get("font", DEFAULT_FONT) not in fonts:
        report.append(f"text '{node['name']}': font '{props.get('font', DEFAULT_FONT)}' is not in the app; drawn with {DEFAULT_FONT}")
        props["font"] = DEFAULT_FONT
    dflt = F.defaults(kind)                                  # a value the layer already has isn't a change (and may not be valid)
    props = {k: v for k, v in props.items() if v != dflt[k]}
    return {**props, "x": box[0] - ox, "y": box[1] - oy, "anchorX": 0.0, "anchorY": 0.0}


def _build(tree: dict, doc_data: dict, into: str, fonts=None, image_dir=None):
    """→ (calls, files, report); files = [(path, PIL image)] for image nodes that carry pixels."""
    taken, calls, files, report = set(index(doc_data, KIND.lists)), [], [], list(tree.get("report", []))

    def walk(nodes, parent, parent_box):
        for node in nodes:
            box = _boxes(node)
            id_ = _id(node.get("name"), node["type"], taken)
            props = _props(node, box, parent_box, fonts, report)
            if node["type"] == "image" and "image" in node:
                if image_dir is None:
                    raise ValueError(f"image '{node['name']}' has pixels but there is nowhere to write them")
                props["src"] = str(Path(image_dir) / f"{id_}.png")
                files.append((props["src"], node["image"]))
            calls.append({"op": "layer.add", "target": [parent],
                          "args": {"type": node["type"], "id": id_, "name": node.get("name") or id_}})
            calls.append({"op": f"{node['type']}.set", "target": [id_], "args": props})
            if node["type"] == "group":
                walk(node["layers"], id_, box)

    walk(tree["layers"], into, [0.0, 0.0, 0.0, 0.0])
    return calls, files, report


def apply_calls(tree: dict, doc_data: dict, into: str, fonts: set | None = None, image_dir=None) -> list[dict]:
    """The calls that put the tree into comp/group `into` (image nodes with pixels need `image_dir`)."""
    return _build(tree, doc_data, into, fonts, image_dir)[0]


def prepare(doc, tree: dict, into: str, fonts: set | None = None) -> tuple[list[dict], list[str]]:
    """The calls that put the tree into `into` and the report; images are written to <doc folder>/imports/<stem>/ first."""
    folder = Path(doc.folder) if doc.folder else None
    image_dir = folder / "imports" / Path(tree["name"]).stem if folder else None
    calls, files, report = _build(tree, doc.data, into, fonts, image_dir)
    for path, img in files:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        img.save(path)
    return calls, report


def import_into(doc, tree: dict, into: str, who, fonts: set | None = None) -> list[str]:
    """Apply the tree to the document in one step. → the report."""
    calls, report = prepare(doc, tree, into, fonts)
    doc.apply(calls, who, label=f"Import {tree['name']}")
    return report
