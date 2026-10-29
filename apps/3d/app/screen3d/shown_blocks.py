"""Block settings shown on the material (PR5; rostrum3d/graph.py `shown`, graph.set show / hide): the rows a person put
on the material's own settings from its blocks ("Noise · Scale"), so the pattern is changed without opening the
blocks. They sit right under the material's essentials (materials.py `head`), in block order; each is the block's own
row (blocks_qt.block_rows: a ramp's stops, a curve's points, "Set by a wire"), its id `block:<block id>:<setting>`, and
a change is graph.set on that block (one undo step; a drag is written once at the release). No Qt.
"""
from __future__ import annotations

from rostrum3d import graph as G

from .blocks_qt import block_rows, paint_to_stops, text_to_points

PREFIX = "block:"


def is_shown(row_id: str) -> bool:
    return row_id.startswith(PREFIX)


def rows_for(material: dict, facts: dict) -> list[dict]:
    """The material's shown block settings as the kit's rows."""
    g = G.graph_of(material)
    linked = set(G.wires_into(g))
    out = []
    for b, kind, name in G.shown(material):
        mine = {k.split(".")[1] for k in linked if k.split(".")[0] == b["id"]}
        for r in block_rows(kind, G.values(material, b), facts, mine):
            if r.get("row") == "param" and r["id"] == name:
                out.append({**r, "id": f'{PREFIX}{b["id"]}:{name}', "label": f'{kind.label} · {r.get("label", name)}',
                            "in": ""})
    return out


def call_for(material: dict, row_id: str, value) -> tuple[dict, str]:
    """graph.set for a shown row's new value, and the change's name."""
    bid, name = row_id[len(PREFIX):].split(":", 1)
    kind = G.type_of(G.graph_of(material), bid, "block")
    inp = kind.input(name)
    control = inp.param.control if inp else ""
    if control == "stops" and isinstance(value, dict):
        value = paint_to_stops(value)
    elif control == "points" and isinstance(value, str):
        value = text_to_points(value)
    return ({"op": "graph.set", "target": [material["id"]], "args": {"block": bid, "values": {name: value}}},
            f'{kind.label}: {inp.param.label if inp else name}')
