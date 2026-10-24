"""What the timeline asks of its rows besides drawing them: is anything keyed, which rows are layers, the frame's cuts.

A binding that reads a bridge's whole `layers` list converts every row (and every key) for QML each time the rows
change, a fifth of an edit's cost on a busy scene. A binding reads these few facts instead (`backend.rowFacts`), which
the bridge announces only when they differ.
"""
from __future__ import annotations


def of(rows: list[dict]) -> dict:
    """{count: how many rows, animated: some row has keys, layerIds: the ids of the rows that are layers, cuts: the first row's frame cuts}."""
    return {"count": len(rows), "animated": any(r.get("keys") for r in rows),
            "layerIds": [r["id"] for r in rows if r["row"] == "layer"],
            "cuts": (rows[0].get("cuts") or []) if rows else []}
