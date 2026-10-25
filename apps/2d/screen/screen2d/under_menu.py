"""Right-click › Select layer ▸ : every layer painted under the pointer (bounds.under_chains, the list Alt+click and the
agents' look_at read), top first, a group's pieces indented under it, the current pick ticked. A row is the layer's name
only: ActionMenu has no icon, and a kind word beside a long name cut the name short (the layout check refuses that). No Qt.
Rows are named `menu:selectLayerMenu` (the parent) and `menu:selectLayer_<id>` (ActionMenu names a row by its value)."""
from __future__ import annotations

PARENT, ROW = "selectLayerMenu", "selectLayer_"
INDENT = " "      # an em space a level


def entries(b, chains: list[list[str]], selected: str) -> list[dict]:
    """[] unless two or more layers are under the pointer; else the one first row {value, label, sub}."""
    if len(chains) < 2:
        return []
    order: list[tuple[str, ...]] = []      # each layer and group once, a group before its pieces, the topmost first
    for c in chains:
        for n in range(1, len(c) + 1):
            if tuple(c[:n]) not in order:
                order.append(tuple(c[:n]))
    at = {p: i for i, p in enumerate(order)}
    order.sort(key=lambda p: [at[p[:n + 1]] for n in range(len(p))])      # the pieces stay under their group
    rows = []
    for path in order:
        item = b.doc.item(path[-1])
        rows.append({"value": ROW + path[-1], "label": INDENT * (len(path) - 1) + b.label_of(item),
                     "checked": path[-1] == selected, "group": "layers"})
    return [{"value": PARENT, "label": "Select layer", "group": "select", "sub": rows}]
