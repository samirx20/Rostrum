"""Which layer a click on the canvas selects, from what is painted under the pointer (bounds.pick_chain: the layer and
its groups, outermost first). No Qt.

- A click selects the outermost group, so a grouped logo moves as one; once you are inside a group (the selection is
  one of its layers), a click picks among that group's layers instead.
- A double-click goes one level in from the selection.
- Ctrl+click picks the piece itself, however deep.
- Alt+click picks the next layer below the pick (`behind`), at the same depth a click works at.
"""
from __future__ import annotations

MODES = ("click", "in", "deep")


def choose(chain: list[str], selected: str, selected_groups: list[str], mode: str) -> str:
    """`chain`: outermost group first, the painted layer last ([] = nothing there). `selected`: the selected layer;
    `selected_groups`: the groups it is in, outermost first."""
    if mode not in MODES:
        raise ValueError(f"pick mode is one of {', '.join(MODES)}; got {mode!r}")
    if not chain:
        return ""
    if mode == "deep":
        return chain[-1]
    if mode == "in" and selected in chain[:-1]:
        return chain[chain.index(selected) + 1]
    inside = [g for g in chain[:-1] if g in selected_groups]
    return chain[chain.index(inside[-1]) + 1] if inside else chain[0]


def levels(chains: list[list[str]], selected: str, selected_groups: list[str], mode: str) -> list[str]:
    """What a click at each of the layers under the pointer (bounds.under_chains, top first) would select at this depth,
    each once (several pieces of one group are the one group)."""
    out: list[str] = []
    for c in chains:
        got = choose(c, selected, selected_groups, mode)
        if got not in out:
            out.append(got)
    return out


def behind(ids: list[str], selected: str) -> str:
    """Alt+click: the one below the pick in `levels`; the top again after the bottom. Nothing picked, or the pick not
    there: the second from the top (just behind what a plain click gets), or the only one."""
    if selected in ids:
        return ids[(ids.index(selected) + 1) % len(ids)]
    return ids[1] if len(ids) > 1 else (ids[0] if ids else "")


def groups_of(doc, item_id: str) -> list[str]:
    """The groups an item is in, outermost first."""
    out, parent = [], doc.parent_of(item_id)[0]
    while doc.item(parent)["type"] != "comp":
        out.insert(0, parent)
        parent = doc.parent_of(parent)[0]
    return out
