"""The block view's rules in Python (no Qt): where a block's ports sit, the kind colours, which wires are allowed (kinds,
one wire per input, no loops) and the add list's search. BLOCKS.md says how an app uses the view.

The view (qml/RostrumKit/BlockView.qml) draws and lights ports with the same rules from `Blocks.js`; an app checks a
wire here before it makes it (`refusal`), and an agent places blocks with `height` / `port_at`. tests/test_blocks.py
runs both sides on the same cases, so they never drift.

Data shapes (BLOCKS.md): a block is {id, type, label, x, y, summary?, note?, inputs: [{name, label, kind, linked?}],
outputs: [{name, label, kind}]}; a wire is {"from": "id.output", "to": "id.input"}; `converts` is {out kind: [input
kinds it may also feed]}.
"""
from __future__ import annotations

import re

WIDTH, HEADER, LINE, TOP, ROW, BOTTOM, PORT = 180, 28, 18, 4, 22, 6, 10    # canvas units; Blocks.js has the same

# A port's colour by kind; an app passes these (or its own) as the view's `kindColours`. Unknown kinds draw grey.
KIND_COLOURS = {
    "colour": "#e3c24f",      # warm yellow: a colour
    "number": "#a3a9b3",      # grey: one number
    "normal": "#8a8cf0",      # blue-violet: a direction
    "style": "#4fc49a",       # green: a stylized setting
    "image": "#e3c24f",       # the Editor's compositing: a picture is a colour per pixel
    "mask": "#c9ccd1",        # light grey: a mask
}


def has_line(b: dict) -> bool:
    return bool(b.get("summary") or b.get("note"))


def rows_top(b: dict) -> int:
    return HEADER + (LINE if has_line(b) else 0) + TOP


def height(b: dict) -> int:
    return rows_top(b) + (len(b.get("outputs", [])) + len(b.get("inputs", []))) * ROW + BOTTOM


def port_at(b: dict, side: str, name: str) -> tuple[float, float] | None:
    """A port's centre in canvas units (the block's x, y added): outputs on the right edge, inputs on the left."""
    outs, ins = b.get("outputs", []), b.get("inputs", [])
    names = [p["name"] for p in (outs if side == "out" else ins)]
    if name not in names:
        return None
    row = names.index(name) + (0 if side == "out" else len(outs))
    return b["x"] + (WIDTH if side == "out" else 0), b["y"] + rows_top(b) + row * ROW + ROW / 2


def port_under(blocks: list[dict], x: float, y: float, reach: float = 11) -> str:
    """"id.in.name" / "id.out.name" of the port within `reach` canvas units of (x, y), the nearest; "" for none."""
    best, found = reach * reach, ""
    for b in blocks:
        for side, ports in (("out", b.get("outputs", [])), ("in", b.get("inputs", []))):
            for p in ports:
                px, py = port_at(b, side, p["name"])
                d = (px - x) ** 2 + (py - y) ** 2
                if d <= best:
                    best, found = d, f"{b['id']}.{side}.{p['name']}"
    return found


def compatible(out_kind: str, in_kind: str, converts: dict | None = None) -> bool:
    """The same kind always; another only as `converts` allows ({"number": ["colour"]})."""
    return out_kind == in_kind or in_kind in (converts or {}).get(out_kind, ())


def block_of(port: str) -> str:
    return port.rsplit(".", 1)[0]


def reach(wires: list[dict], start: str, way: str = "down") -> set[str]:
    """The blocks reachable from `start` along wires, downstream or upstream, `start` included."""
    seen, todo = {start}, [start]
    while todo:
        at = todo.pop()
        for w in wires:
            a, b = block_of(w["from"]), block_of(w["to"])
            nxt = b if way == "down" and a == at else a if way == "up" and b == at else None
            if nxt is not None and nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    return seen


def makes_loop(wires: list[dict], from_id: str, to_id: str, to_port: str = "") -> bool:
    """A wire from block `from_id` into `to_id` closes a loop. The input's old wire (`to_port`) goes, so it doesn't count."""
    kept = [w for w in wires if w["to"] != to_port] if to_port else wires
    return from_id in reach(kept, to_id, "down")


def refusal(blocks: list[dict], wires: list[dict], frm: str, to: str, converts: dict | None = None) -> str:
    """Why the wire `frm` ("id.output") -> `to` ("id.input") can't be made, as a code; "" when it can. Codes: unknown
    (no such block or port), same-block, kind, loop. One wire per input: a new one replaces the old (not a refusal)."""
    by_id = {b["id"]: b for b in blocks}
    a, b = by_id.get(block_of(frm)), by_id.get(block_of(to))
    out = next((p for p in (a or {}).get("outputs", []) if p["name"] == frm.rsplit(".", 1)[-1]), None)
    inp = next((p for p in (b or {}).get("inputs", []) if p["name"] == to.rsplit(".", 1)[-1]), None)
    if out is None or inp is None:
        return "unknown"
    if a["id"] == b["id"]:
        return "same-block"
    if not compatible(out["kind"], inp["kind"], converts):
        return "kind"
    return "loop" if makes_loop(wires, a["id"], b["id"], to) else ""


def first_input(entry: dict, out_kind: str, converts: dict | None = None) -> str:
    """The input of a catalogue entry (or block) a wire of `out_kind` goes into when the add list made it from a dropped
    wire: the first of the same kind, else the first it may feed; "" for none."""
    ins = entry.get("inputs", [])
    same = next((p["name"] for p in ins if p["kind"] == out_kind), "")
    return same or next((p["name"] for p in ins if compatible(out_kind, p["kind"], converts)), "")


def _starts_all(words: list[str], text: str) -> bool:
    return all(re.search(r"(^|[^a-z0-9])" + re.escape(w), text) for w in words)


def rank(entry: dict, q: str, words: list[str]) -> int:
    """0: the label starts with the query; 1: every word starts a word of the label; 2: ... of label, group or `words`;
    -1: no match."""
    label = entry["label"].lower()
    if label.startswith(q):
        return 0
    if _starts_all(words, label):
        return 1
    return 2 if _starts_all(words, f"{label} {entry.get('group', '')} {entry.get('words', '')}".lower()) else -1


def search(catalogue: list[dict], query: str, from_kind: str = "", converts: dict | None = None) -> list[dict]:
    """The add list: entries matching the query, best first, catalogue order within a rank; an empty query lists all.
    `from_kind` (a wire dropped on empty space) keeps only the types with an input it may feed."""
    q = " ".join(str(query or "").lower().split())
    words = q.split()
    hits = []
    for i, e in enumerate(catalogue):
        if from_kind and not any(compatible(from_kind, p["kind"], converts) for p in e.get("inputs", [])):
            continue
        r = rank(e, q, words) if q else 0
        if r >= 0:
            hits.append((r, i))
    return [catalogue[i] for _, i in sorted(hits)]
