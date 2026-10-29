"""A material's blocks graph (brief 23): the data, the wire rules and what the screen and agents read (describe).

A material item holds its graph in one field, `blocks` (absent or empty = no graph; Surface is always there):
    {"blocks": [{"id": "noise_1", "type": "noise", "x": -320, "y": 40, "values": {"scale": 8}}],
     "wires":  [{"from": "noise_1.value", "to": "surface.roughness"}],
     "surface": {"x": 0, "y": 0}}
Wire rules: the same kind always; number → colour (grey) and colour → number (its brightness); normal and style only
to their own kind. One wire per input; an output feeds any number of inputs; no loops. A stylized block's values are
the material's own fields (graph_blocks.py), never kept in the block; it is on while wired into Surface's Style,
directly or through other stylized blocks. The ops are ops_graph.py, the MaterialX document graph_mtlx.py.
"""
from __future__ import annotations

import copy
import re

from . import graph_blocks as B

FIELD = "blocks"
SURFACE = "surface"
BLOCK_ID = re.compile(r"^[A-Za-z][A-Za-z0-9]*(_[A-Za-z0-9]+)*$")    # a MaterialX / USD name; "__" is the writer's
CAST = {("number", "colour"), ("colour", "number")}                   # the two wires between kinds (grey, brightness)


class GraphError(ValueError):
    def __init__(self, subject: str, problem: str, hint: str | None = None, accepted=()):
        super().__init__(f"{subject} {problem}")
        self.subject, self.problem, self.hint, self.accepted = subject, problem, hint, list(accepted)


def graph_of(material: dict) -> dict:
    """The material's graph, every part present (a copy: change it and write it back). A stylized setting that is on
    without its block (a starting point, material.set, a script) gets one, wired into Surface's Style, so the view
    always shows what the material does."""
    g = copy.deepcopy(material.get(FIELD) or {})
    g = {"blocks": g.get("blocks", []), "wires": g.get("wires", []), "surface": g.get("surface", {"x": 0, "y": 0})}
    have = {b["type"] for b in g["blocks"]}
    missing = [t for t, field in B.STYLIZED.items() if material.get(field) and t not in have]
    taken = {b["id"] for b in g["blocks"]}
    for k, type_ in enumerate(missing):
        bid = next(f"{type_}_{n}" for n in range(1, 10**6) if f"{type_}_{n}" not in taken)
        taken.add(bid)
        g["blocks"].append({"id": bid, "type": type_, "x": g["surface"].get("x", 0) - 300,
                            "y": g["surface"].get("y", 0) + 140 + 160 * k})
        chain = style_chain(g)                   # at the end of the Style chain: taking it out breaks no other
        g["wires"].append({"from": f"{bid}.style", "to": f"{chain[-1]}.{B.CHAIN}" if chain else f"{SURFACE}.style"})
    return g


def has_graph(material: dict) -> bool:
    g = material.get(FIELD) or {}
    return bool(g.get("blocks") or g.get("wires"))


def blocks_by_id(g: dict) -> dict:
    return {b["id"]: b for b in g["blocks"]}


def wires_into(g: dict) -> dict:
    """{"block.input": "block.output"}: what feeds each linked input."""
    return {w["to"]: w["from"] for w in g["wires"]}


def split(port: str, where: str) -> tuple[str, str]:
    if not isinstance(port, str) or port.count(".") != 1 or not all(port.split(".")):
        raise GraphError(f'{where} "{port}"', 'is not "block.port"', 'Write the block id and the port name, like '
                         '"noise_1.value" or "surface.roughness".')
    a, b = port.split(".")
    return a, b


def type_of(g: dict, block_id: str, where: str) -> B.Block:
    if block_id == SURFACE:
        return B.SURFACE
    b = blocks_by_id(g).get(block_id)
    if b is None:
        raise GraphError(f'{where} "{block_id}"', "is not a block of this material",
                         accepted=[SURFACE, *blocks_by_id(g)])
    return B.BY_TYPE[b["type"]]


def port_kind(g: dict, port: str, side: str) -> str:
    """The kind of an output (`side` "from") or a linkable input ("to"); loud for an unknown one."""
    bid, name = split(port, side)
    kind = type_of(g, bid, side)
    if side == "from":
        out = kind.output(name)
        if out is None:
            raise GraphError(f'from "{port}"', f"is not an output of {kind.label}", accepted=[o[0] for o in kind.outputs]
                             or ["(Surface has no outputs)"])
        return out[2]
    inp = kind.input(name)
    if inp is None or not inp.kind:
        raise GraphError(f'to "{port}"', f"is not an input a wire can feed on {kind.label}",
                         accepted=[i.name for i in kind.inputs if i.kind])
    return inp.kind


def fits(from_kind: str, to_kind: str) -> bool:
    return from_kind == to_kind or (from_kind, to_kind) in CAST


def downstream(g: dict, start: str) -> set[str]:
    """Every block fed, directly or not, by block `start` (its own id included)."""
    seen, todo = {start}, [start]
    while todo:
        cur = todo.pop()
        for w in g["wires"]:
            if w["from"].split(".")[0] == cur and (nxt := w["to"].split(".")[0]) not in seen:
                seen.add(nxt)
                todo.append(nxt)
    return seen


def check_wire(g: dict, frm: str, to: str) -> None:
    """A new wire's problems, loudly: names, kinds, a loop (the old wire into `to` is replaced, never counted)."""
    fk, tk = port_kind(g, frm, "from"), port_kind(g, to, "to")
    if not fits(fk, tk):
        raise GraphError(f'wire {frm} to {to}', f"joins a {fk} output to a {tk} input",
                         "Colour and number join either way; a normal or style output only feeds a normal or style input.")
    src, dst = frm.split(".")[0], to.split(".")[0]
    if src == dst or src in downstream({"wires": [w for w in g["wires"] if w["to"] != to]}, dst):
        raise GraphError(f'wire {frm} to {to}', "would make a loop (a block feeding itself)",
                         "Wire blocks one way only, towards Surface.")


def check_value(block_type: str, name: str, value, where: str):
    """A block value checked by its input's Param (raises RostrumError, the ops' own words); curve points 2..8 in 0..1."""
    kind = B.get(block_type)
    inp = kind.input(name) if kind else None
    if inp is None or name == B.CHAIN:
        raise GraphError(f'{where} "{name}"', f"is not a setting of {kind.label if kind else block_type}",
                         accepted=[i.name for i in kind.inputs if i.name != B.CHAIN] if kind else [])
    value = inp.param.check(value, where)
    if block_type == "curve" and name == "points":
        if not 2 <= len(value) <= 8 or any(not (0 <= c <= 1) for q in value for c in q):
            raise GraphError(f"{where} points", "must be 2 to 8 points with x and y from 0 to 1")
        value = sorted(value)
    return value


def values(material: dict, block: dict) -> dict:
    """A block's values with defaults; a stylized block's are the material's own fields."""
    kind = B.BY_TYPE[block["type"]]
    if block["type"] in B.STYLIZED:
        from . import fields as F
        d = F.defaults("material")
        return {i.name: material.get(i.name, d.get(i.name)) for i in kind.inputs if i.name != B.CHAIN}
    return {**kind.defaults(), **block.get("values", {})}


def showable(kind: B.Block) -> list[str]:
    """The settings of a block that may be shown on the material (PR5): its own numbers, colours and choices; never
    Surface's or a stylized block's (those are the material's own rows already) nor the Style chain."""
    if kind.type == "surface" or kind.type in B.STYLIZED:
        return []
    return [i.name for i in kind.inputs if i.name != B.CHAIN]


def shown(material: dict) -> list[tuple[dict, B.Block, str]]:
    """The settings shown on the material (a block's `shown`, in block order then the block's own order): each
    (block, its type, setting). A name the block's type no longer has is skipped (kept in the data)."""
    out = []
    for b in graph_of(material)["blocks"]:
        kind = B.BY_TYPE[b["type"]]
        names = set(b.get("shown") or ()) & set(showable(kind))
        out += [(b, kind, n) for n in showable(kind) if n in names]
    return out


def style_chain(g: dict) -> list[str]:
    """The stylized blocks that are on: wired into Surface's Style, directly or through each other's Style."""
    into, on, port = wires_into(g), [], f"{SURFACE}.style"
    while port in into and (bid := into[port].split(".")[0]) not in on:
        on.append(bid)
        port = f"{bid}.{B.CHAIN}"
    return on


def toggles(g: dict) -> dict:
    """{material toggle field: on?} for every stylized block in the graph (the fold compile and the ops apply)."""
    on, out = set(style_chain(g)), {}
    for b in g["blocks"]:
        if b["type"] in B.STYLIZED:
            out[B.STYLIZED[b["type"]]] = out.get(B.STYLIZED[b["type"]], False) or b["id"] in on
    return out


def problems(material: dict) -> list[str]:
    """The whole-document check of one material's graph (kind.check): ids, types, values, wires, loops."""
    if not material.get(FIELD):
        return []
    mid, out, seen = material.get("id"), [], set()
    g = graph_of(material)
    for b in g["blocks"]:
        bid = b.get("id")
        if not isinstance(bid, str) or not BLOCK_ID.match(bid) or bid == SURFACE or bid in seen:
            out.append(f'{mid}.blocks: block id {bid!r} is taken or not letters, digits and single _')
        seen.add(bid)
        if b.get("type") not in B.BY_TYPE:
            out.append(f'{mid}.blocks: {bid} is a {b.get("type")!r}, not a block type ({", ".join(B.BY_TYPE)})')
            continue
        for k, v in (b.get("values") or {}).items():
            try:
                check_value(b["type"], k, v, f"{mid}.{bid}")
            except Exception as e:          # GraphError or the Param's RostrumError: both in words
                out.append(str(e))
    if out:
        return out
    taken = set()
    for w in g["wires"]:
        try:
            if w["to"] in taken:
                raise GraphError(f'wire into {w["to"]}', "is the second one (one wire per input)")
            check_wire({**g, "wires": [x for x in g["wires"] if x is not w]}, w["from"], w["to"])
            taken.add(w["to"])
        except GraphError as e:
            out.append(f"{mid}.blocks: {e}")
    return out


def _summary(kind: B.Block, vals: dict, linked: set) -> str:
    n = kind.summary
    if not n or n in linked:
        return ""
    v = vals.get(n)
    if n == "file":
        return (v or "").replace("\\", "/").rsplit("/", 1)[-1] or "No picture"
    if n == "stops":
        return f"{len(v)} stops"
    if n == "points":
        return f"{len(v)} points"
    inp = kind.input(n)
    if inp.param.type == "choice":
        return inp.param.option_label(v)
    return f"{inp.param.label} {v:g}{inp.param.unit and ' ' + inp.param.unit}" if isinstance(v, (int, float)) else ""


def _block_row(kind: B.Block, bid: str, x, y, vals: dict, into: dict, removable: bool) -> dict:
    linked = {k.split(".")[1] for k in into if k.split(".")[0] == bid}
    return {"id": bid, "type": kind.type, "label": kind.label, "x": x, "y": y,
            "summary": _summary(kind, vals, linked), **({"note": kind.note} if kind.note else {}),
            "removable": removable,
            "inputs": [{**p, "linked": p["name"] in linked} for p in B.ports(kind.inputs)],
            "outputs": [{"name": n, "label": lab, "kind": k} for n, lab, k in kind.outputs],
            "values": vals}


def describe(material: dict, catalogue: bool = True) -> dict:
    """CONTRACT §4's `blocks` / `wires` / `catalogue` for the kit view (and look_material). Each block also carries
    its `values` (defaults filled in); Surface's are the material's linkable fields; a stylized block's `on`."""
    from . import fields as F
    g, d = graph_of(material), F.defaults("material")
    into, on = wires_into(g), set(style_chain(g))
    surf_vals = {n: material.get(n, d.get(n)) for n in B.SURFACE_PORTS if n in d}
    rows = [_block_row(B.SURFACE, SURFACE, g["surface"].get("x", 0), g["surface"].get("y", 0), surf_vals, into, False)]
    for b in g["blocks"]:
        row = _block_row(B.BY_TYPE[b["type"]], b["id"], b.get("x", 0), b.get("y", 0), values(material, b), into, True)
        if b["type"] in B.STYLIZED:
            row["on"] = b["id"] in on
        if b.get("shown"):
            row["shown"] = list(b["shown"])           # settings shown as rows on the material (graph.set show)
        rows.append(row)
    out = {"blocks": rows, "wires": [{"from": w["from"], "to": w["to"]} for w in g["wires"]]}
    return {**out, "catalogue": B.catalogue()} if catalogue else out


def final_only(material: dict) -> list[str]:
    """Why a graph needs Final to be seen: its Final-only blocks (Bevel shading, Ambient occlusion) that feed anything."""
    g = graph_of(material)
    fed = {w["from"].split(".")[0] for w in g["wires"]}
    return [f'{b["id"]} ({B.BY_TYPE[b["type"]].label}) shows in Final only' for b in g["blocks"]
            if b["id"] in fed and B.BY_TYPE[b["type"]].note == "Final only"]


def text(material: dict) -> str:
    """The graph in a few plain lines (look_material's reply): each block with its summary, then each wire."""
    if not has_graph(material):
        return ""
    d = describe(material, catalogue=False)
    rows = [f'{b["id"]} ({b["label"]}' + (f', {b["summary"]}' if b["summary"] else "") + (", on" if b.get("on") else "")
            + (f', shown on the material: {", ".join(b["shown"])}' if b.get("shown") else "") + ")" for b in d["blocks"][1:]]
    return "Blocks: " + "; ".join(rows) + ". Wires: " + "; ".join(f'{w["from"]} → {w["to"]}' for w in d["wires"]) + "."
