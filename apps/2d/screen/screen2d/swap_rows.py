"""A swap set's `show` row in the inspector: a choice among the set's own children, by name, never a bare number.
The kit fills dynamic options only for list params, so 2D turns the row into a choice itself. The choice's values are
the children's places as text ("0", "1" …: the kit's choice field reads a 0 as empty); `edit_value` turns the pick
back into the number the field takes. No Qt."""
from __future__ import annotations

from rostrum2d.swap import index_at

from .outline import label_of


def is_swap(item: dict | None) -> bool:
    return bool(item) and item.get("type") == "group" and bool(item.get("swap"))


def rows(rows: list[dict], item: dict | None, t: float) -> list[dict]:
    """The inspector rows of `item` with its `show` row made a choice of its children, the one showing at time t current."""
    if not is_swap(item):
        return rows
    kids = item.get("layers", [])
    options = [{"value": str(i), "label": label_of(c)} for i, c in enumerate(kids)]
    current = str(index_at(item, t, len(kids))) if kids else ""
    return [{**r, "type": "choice", "options": options, "value": current, "min": None, "max": None, "unit": ""}
            if r["row"] == "param" and r["id"] == "show" else r for r in rows]


def edit_value(item: dict, param: str, value):
    """The value an inspector pick sends: `show`'s text place as a whole number; anything else as it is."""
    return int(value) if is_swap(item) and param == "show" and isinstance(value, str) else value
