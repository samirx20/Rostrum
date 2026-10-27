"""A table of data (CSV, TSV, semicolon-separated, or a JSON list of objects) as rows: one dict per row, keyed by the
header, numbers already numbers ("1,284.5" and "12%" stay words; clean them in the file or the script). Scripts get
parse_table for a table pasted as text; read_table and the inspect_table tool read a file."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path


def _value(cell: str):
    s = cell.strip()
    try:
        n = float(s)
    except ValueError:
        return s
    return int(n) if n.is_integer() and "." not in s and "e" not in s.lower() else n


def parse_table(text: str) -> list[dict]:
    """CSV text (a header row, then one row per line; comma, tab or semicolon between cells) -> [{column: value}, …].
    Number cells are numbers, empty cells are "" and blank lines are skipped."""
    lines = [ln for ln in str(text).strip().splitlines() if ln.strip()]
    if not lines:
        return []
    sep = max(",\t;", key=lines[0].count)
    head, *body = list(csv.reader(io.StringIO("\n".join(lines)), delimiter=sep))
    head = [h.strip() for h in head]
    if len(set(head)) != len(head) or "" in head:
        raise ValueError(f"parse_table: the header row needs one different name per column; it is {head}")
    rows = []
    for n, cells in enumerate(body, 2):
        if len(cells) > len(head):
            raise ValueError(f"parse_table: line {n} has {len(cells)} cells, the header has {len(head)}")
        rows.append({h: _value(c) for h, c in zip(head, cells + [""] * (len(head) - len(cells)))})
    return rows


def read_table(path) -> list[dict]:
    """A .csv / .tsv / .txt file, or a .json list of objects, as rows (parse_table)."""
    p = Path(path)
    text = p.read_text(encoding="utf-8-sig")
    if p.suffix.lower() == ".json":
        rows = json.loads(text)
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise ValueError(f"{p.name}: a JSON table is a list of objects ([{{\"name\": …, \"value\": …}}, …])")
        return rows
    return parse_table(text)


def columns(rows: list[dict]) -> list[dict]:
    """Each column: its name and, when every filled cell is a number, its min and max."""
    out = []
    for name in (rows[0] if rows else {}):
        vals = [r.get(name) for r in rows if r.get(name) != ""]
        col = {"name": name}
        if vals and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
            col.update(min=min(vals), max=max(vals))
        out.append(col)
    return out
