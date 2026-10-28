"""Which of the new scene's lights a script's own lights replace (start_scene.py: `sky` the Studio dome, `key_light` and
`rim_light` the two panels). A script's own lights ADD to the start's: the start key and rim stay, so a light made too
dim never leaves the picture black. `light(..., replace_start_lights=True)` takes the start key and rim out (and the
sky too when the script makes a dome), so its lighting is the only lighting. A dome of the script's own always takes the
start sky out (there is one sky). `edit("sky", …)` or making `sky` again changes that one light and is not "a light of
its own". Applied in script.Build.take_over, before the merge, as a removal the run owns (one undo step); the
run_script reply names what was removed.
"""
from __future__ import annotations


def _walk(nodes):
    for n in nodes:
        yield n
        yield from _walk(n.get("children", []))


def _kind(node: dict) -> str:
    return "dome" if node.get("kind") == "dome" else "panel"


def replaced(doc, made_items: list, start_has, replace: bool = False) -> list[str]:
    """Ids of start lights still in the document that the lights in `made_items` replace: the start sky when they hold
    a dome; with `replace` (replace_start_lights=True), the start key and rim too when they hold any other light.
    `start_has(id, "items")`: whether the new scene made that id and it is still there."""
    mine = {_kind(n) for n in _walk(made_items) if n.get("type") == "light"}
    if not replace:
        mine &= {"dome"}
    if not mine:
        return []
    made = {n["id"] for n in _walk(made_items)}
    out = []
    for n in _walk(doc.data.get("items", [])):
        if n.get("type") == "light" and n["id"] not in made and _kind(n) in mine and start_has(n["id"], "items"):
            out.append(n["id"])
    return out
