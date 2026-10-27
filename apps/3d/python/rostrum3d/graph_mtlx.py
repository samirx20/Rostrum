"""A material's blocks graph → its MaterialX 1.39 document (brief 23, CONTRACT §3), which the core reads with USD's
MaterialX reader: Storm draws the nodegraph through the Rostrum library's nodegraphs, Cycles maps each block to its
own node (core/src/material_blocks.cpp).

    <nodegraph name="NG_blocks"> one rostrum_<type> node per block output in use (node name = block id; a second
        output of the same block: <id>__<output>), every input written (a value, or nodename + output when wired),
        a rostrum_grey / rostrum_brightness node (<to>__<input>) where a number feeds a colour or the other way,
        one <output> per wired Surface input, named after it (baseColor, roughness, metallic, emissionColor, normal)
    <UsdPreviewSurface name="surface"> its inputs from NG_blocks (USD's reader drops a nodegraph no material uses)
    <surfacematerial name="M_<material id>">
    the stylized blocks as rostrum_<type> nodes of type rostrum_style, for interchange (their values = the material's)

The input table (`inputs`) is the one source for both the document and the library's nodedefs
(apps/3d/tools/make_blocks_mtlx.py writes core/mtlx/rostrum_blocks.mtlx and stylized/mtlx/rostrum_stylized.mtlx).
Documents are named by their content, <folder>/blocks/<material id>-<sha1 12>.mtlx (USD caches a layer by path).
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from xml.sax.saxutils import quoteattr

from . import graph as G
from . import graph_blocks as B
from .colors import linear

PREVIEW = {"baseColor": ("diffuseColor", "color3"), "roughness": ("roughness", "float"),
           "metallic": ("metallic", "float"), "emissionColor": ("emissiveColor", "color3"),
           "normal": ("normal", "vector3")}
INDEX = {("mix", "blend"): "blendIndex", ("ramp", "interpolate"): "interpolateIndex"}   # Storm's twin of a choice
MAX_STOPS = 8


def node_name(block_type: str) -> str:
    return B.get(block_type).mtlx


def _fmt(t: str, v) -> str:
    if t == "color3":
        return ", ".join(f"{c:.6g}" for c in linear(v))
    if t == "boolean":
        return "true" if v else "false"
    if t == "float":
        return f"{float(v):.6g}"
    if t == "integer":
        return str(int(v))
    return str(v)


def _stops(prefix: str, t: str, pts: list) -> list[tuple]:
    pts = sorted(pts, key=lambda p: p[0])[:MAX_STOPS]
    pad = pts + [pts[-1]] * (MAX_STOPS - len(pts))
    out = [("count", "integer", len(pts))]
    out += [(f"pos{i}", "float", 1.0 if i > len(pts) else p[0]) for i, p in enumerate(pad, 1)]
    out += [(f"{prefix}{i}", t, p[1]) for i, p in enumerate(pad, 1)]
    return out


def inputs(block_type: str, vals: dict) -> list[tuple[str, str, object]]:
    """Every MaterialX input of a block, (name, type, value) in order: its library nodedef and its document node."""
    kind, out = B.get(block_type), []
    for inp in kind.inputs:
        p, v = inp.param, vals.get(inp.name, inp.param.default)
        if inp.name == B.CHAIN:
            out.append((B.CHAIN, "rostrum_style", None))
        elif p.control == "stops":
            out += _stops("col", "color3", v)
        elif p.control == "points":
            out += _stops("val", "float", v)
        elif inp.kind:
            out.append((inp.name, B.KINDS[inp.kind], v))
        elif p.type == "number":
            out.append((inp.name, "integer" if p.integer else "float", v))
        elif p.type == "color":
            out.append((inp.name, "color3", v))
        elif p.type == "toggle":
            out.append((inp.name, "boolean", bool(v)))
        elif p.type == "choice":
            out.append((inp.name, "string", v))
            if (block_type, inp.name) in INDEX:
                out.append((INDEX[block_type, inp.name], "integer", p.options.index(v)))
        else:
            out.append((inp.name, "filename" if p.control == "file" else "string", v or ""))
    return out


def _input(name, t, value=None, link=None, extra="") -> str:
    if link:
        node, output = link
        return f'<input name="{name}" type="{t}" nodename="{node}"' + (f' output="{output}"' if output else "") + "/>"
    return f'<input name="{name}" type="{t}" value={quoteattr(_fmt(t, value))}{extra}/>'


class _Writer:
    def __init__(self, material: dict):
        self.m, self.g = material, G.graph_of(material)
        self.by_id, self.into = G.blocks_by_id(self.g), G.wires_into(self.g)
        self.lines: list[str] = []
        used: dict[str, list[str]] = {}
        for w in self.g["wires"]:
            bid, out = w["from"].split(".")
            used.setdefault(bid, [])
            if out not in used[bid]:
                used[bid].append(out)
        self.used = used

    def node_of(self, port: str) -> tuple[str, str]:
        """(document node name, output name) of a block output."""
        bid, out = port.split(".")
        return (bid if self.used[bid][0] == out else f"{bid}__{out}"), B.out_name(self.by_id[bid]["type"], out)

    def link(self, src: str, to_node: str, to_input: str, to_kind: str) -> tuple[str, str]:
        """The link into an input: straight, or through a grey / brightness node when the kinds differ."""
        node, out = self.node_of(src)
        frm = G.port_kind(self.g, src, "from")
        if frm == to_kind:
            return node, out
        conv = f"{to_node}__{to_input}"
        cat, t, it = ("rostrum_grey", "color3", "float") if to_kind == "colour" else ("rostrum_brightness", "float", "color3")
        self.lines.append(f'    <{cat} name="{conv}" type="{t}">{_input("in", it, link=(node, out))}</{cat}>')
        return conv, "out"

    def block(self, b: dict) -> None:
        kind = B.BY_TYPE[b["type"]]
        vals = G.values(self.m, b)
        for out in self.used.get(b["id"]) or [kind.outputs[0][0]]:
            name = b["id"] if out == (self.used.get(b["id"]) or [out])[0] else f'{b["id"]}__{out}'
            t = B.KINDS[kind.output(out)[2]]
            ins = []
            for n, it, v in inputs(b["type"], vals):
                src = self.into.get(f'{b["id"]}.{n}')
                if src:
                    ins.append(_input(n, it, link=self.link(src, name, n, kind.input(n).kind)))
                elif it != "rostrum_style":
                    cs = ' colorspace="srgb_texture"' if it == "filename" and vals.get("colourData") == "colour" else ""
                    ins.append(_input(n, it, v, extra=cs))
            self.lines.append(f'    <{kind.mtlx} name="{name}" type="{t}">' + "".join(ins) + f"</{kind.mtlx}>")

    def text(self) -> str | None:
        surf = {to.split(".")[1]: src for to, src in self.into.items() if to.startswith("surface.") and not to.endswith(".style")}
        if not surf:
            return None                     # nothing for a renderer to draw: the stylized fields alone say it
        for b in self.g["blocks"]:
            if b["type"] not in B.STYLIZED:
                self.block(b)
        outs = [f'    <output name="{n}" type="{PREVIEW[n][1]}" nodename="{nd}" output="{o}"/>'
                for n in PREVIEW if n in surf for nd, o in [self.link(surf[n], "surface", n, B.SURFACE_PORTS[n])]]
        graph = self.lines
        prev = "".join(f'<input name="{PREVIEW[n][0]}" type="{PREVIEW[n][1]}" nodegraph="NG_blocks" output="{n}"/>'
                       for n in PREVIEW if n in surf)
        style = []
        for b in self.g["blocks"]:
            if b["type"] in B.STYLIZED:
                vals = G.values(self.m, b)
                src = self.into.get(f'{b["id"]}.{B.CHAIN}')
                ins = "".join(_input(n, t, link=(src.split(".")[0], "style")) if t == "rostrum_style" else _input(n, t, v)
                              for n, t, v in inputs(b["type"], vals) if t != "rostrum_style" or src)
                style.append(f'  <{B.BY_TYPE[b["type"]].mtlx} name="{b["id"]}" type="rostrum_style">{ins}'
                             f'</{B.BY_TYPE[b["type"]].mtlx}>')
        return "\n".join(['<?xml version="1.0"?>', '<materialx version="1.39">', '  <nodegraph name="NG_blocks">',
                          *graph, *outs, "  </nodegraph>",
                          f'  <UsdPreviewSurface name="surface" type="surfaceshader">{prev}</UsdPreviewSurface>',
                          f'  <surfacematerial name="M_{self.m["id"]}" type="material">'
                          '<input name="surfaceshader" type="surfaceshader" nodename="surface"/></surfacematerial>',
                          *style, "</materialx>", ""])


def document(material: dict) -> str | None:
    """The material's MaterialX document, or None when no block feeds Surface (nothing to draw)."""
    return _Writer(material).text() if G.has_graph(material) else None


def blocks_dir(folder) -> Path:
    """Where documents go: <folder>/blocks, or the shared cache's blocks folder for a document outside a project."""
    if folder:
        return Path(folder) / "blocks"
    from rostrum_core.cache import CACHE
    return CACHE.root / "blocks"


def write_document(material: dict, folder) -> str | None:
    """Write the material's document (when it has one) as <folder>/blocks/<id>-<sha1 12>.mtlx, remove its older ones,
    and return the absolute path; None when the graph feeds nothing. The scene's and the live `material` request's
    props carry it as "blocks"."""
    text = document(material)
    if text is None:
        return None
    where = blocks_dir(folder)
    where.mkdir(parents=True, exist_ok=True)
    path = where / f'{material["id"]}-{hashlib.sha1(text.encode()).hexdigest()[:12]}.mtlx'
    if not path.exists():
        tmp = path.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    for old in where.glob(f'{material["id"]}-*.mtlx'):
        if old != path:
            old.unlink(missing_ok=True)
    return str(path.resolve())
